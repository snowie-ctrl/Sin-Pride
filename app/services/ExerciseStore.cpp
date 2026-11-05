#include "services/ExerciseStore.h"

#include <QBuffer>
#include <QDebug>
#include <QDir>
#include <QFile>
#include <QImageReader>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkReply>
#include <QRegularExpression>
#include <QSaveFile>
#include <QUrl>
#include <QUrlQuery>

#include <utility>

#include "api/AuthNetworkFactory.h"


ExerciseStore::ExerciseStore(Api &api, const QString &root, QObject *parent)
    : QObject(parent), m_api(api), m_root(root), m_network(new AuthNetworkAccessManager(this))
{
    load();
    // Back from an outage: pictures that had no answer are asked for again by whatever shows them.
    connect(&m_api, &Api::onlineChanged, this, [this]() {
        if (!m_api.online())
            return;
        ++m_pictureRevision;
        emit picturesChanged();
    });
    // A new session (signed in, or someone else): a picture refused without one may come now. Only what is still
    // on its way stays asked.
    connect(&m_api, &Api::sessionTokenChanged, this, [this]() {
        m_asked = m_inFlight;
        for (const QString &name : std::as_const(m_queue))
            m_asked.insert(name);
        ++m_pictureRevision;
        emit picturesChanged();
    });
}

bool ExerciseStore::validPictureName(const QString &name)
{
    static const QRegularExpression valid(QStringLiteral("^[0-9a-f]{20}\\.jpg$"));
    return valid.match(name).hasMatch();
}

QString ExerciseStore::catalogFile() const
{
    return m_root + QStringLiteral("/catalog/catalog.json");
}

QString ExerciseStore::pictureFolder() const
{
    return m_root + QStringLiteral("/catalog/pictures");
}

QString ExerciseStore::pictureFile(const QString &name) const
{
    return pictureFolder() + QLatin1Char('/') + name;
}

QVariantMap ExerciseStore::exercise(int id) const
{
    const auto it = m_index.constFind(id);
    return it == m_index.constEnd() ? QVariantMap() : m_exercises.at(*it);
}

void ExerciseStore::load()
{
    QFile file(catalogFile());
    if (!file.open(QIODevice::ReadOnly))
        return;
    const QJsonDocument doc = QJsonDocument::fromJson(file.readAll());
    // A copy that does not read whole (a crash mid-write, a hand edit) is no copy: the next refresh asks for all of it.
    if (!doc.isObject() || !adopt(doc.object()))
        qWarning() << "[catalog] the copy on this device could not be read; it will be fetched again";
}

bool ExerciseStore::adopt(const QJsonObject &data)
{
    const QJsonValue list = data.value("exercises");
    const QJsonValue version = data.value("version");
    if (!list.isArray() || !(version.isString() || version.isNull()))
        return false;
    QList<QVariantMap> exercises;
    QHash<int, int> index;
    for (const QJsonValue &value : list.toArray()) {
        const QJsonObject e = value.toObject();
        const int id = e.value("id").toInt();
        if (id <= 0 || e.value("name").toString().trimmed().isEmpty() || index.contains(id))
            return false;
        index.insert(id, int(exercises.size()));
        exercises.append(e.toVariantMap());
    }
    m_version = version.toString();
    m_exercises = std::move(exercises);
    m_index = std::move(index);
    ++m_revision;
    emit changed();
    return true;
}

void ExerciseStore::save() const
{
    QJsonArray list;
    for (const QVariantMap &e : m_exercises)
        list.append(QJsonObject::fromVariantMap(e));
    const QJsonObject data{{"version", m_version.isEmpty() ? QJsonValue() : QJsonValue(m_version)}, {"exercises", list}};
    QDir().mkpath(m_root + QStringLiteral("/catalog"));
    // Written whole or not at all, so a crash never leaves half a catalog.
    QSaveFile out(catalogFile());
    if (!out.open(QIODevice::WriteOnly) || out.write(QJsonDocument(data).toJson(QJsonDocument::Compact)) < 0
        || !out.commit())
        qWarning() << "[catalog] could not keep the catalog on this device";
}

void ExerciseStore::prunePictures()
{
    QSet<QString> named;
    for (const QVariantMap &e : std::as_const(m_exercises))
        for (const QVariant &picture : e.value("pictures").toList())
            named.insert(picture.toString());
    QDir folder(pictureFolder());
    for (const QString &name : folder.entryList({QStringLiteral("*.jpg")}, QDir::Files))
        if (!named.contains(name))
            folder.remove(name);
}

void ExerciseStore::refresh()
{
    if (m_loading) {
        m_refreshAgain = true;
        return;
    }
    m_loading = true;
    m_error.clear();
    emit loadingChanged();
    QUrlQuery query;
    if (!m_version.isEmpty())
        query.addQueryItem(QStringLiteral("version"), m_version);
    m_api.get(QStringLiteral("/catalog"), query, [this](const Api::Result &result) {
        m_loading = false;
        if (!result.ok) {
            m_error = reasonOf(result);
        } else {
            const QJsonObject data = result.object.value("data").toObject();
            if (!data.value("unchanged").toBool()) {
                if (adopt(data)) {
                    save();
                    prunePictures();
                } else {
                    m_error = QStringLiteral("The server sent a catalog this app cannot read");
                }
            }
        }
        emit loadingChanged();
        if (std::exchange(m_refreshAgain, false))
            refresh();
    });
}

QString ExerciseStore::pictureUrl(const QString &name)
{
    if (!validPictureName(name))
        return {};
    const QString file = pictureFile(name);
    if (QFile::exists(file))
        return QUrl::fromLocalFile(file).toString();
    if (!m_asked.contains(name) && !m_api.pictureUrl(name).isEmpty()) {
        m_asked.insert(name);
        m_queue.append(name);
        fetchNext();
    }
    return {};
}

void ExerciseStore::fetchNext()
{
    while (m_inFlight.size() < Parallel && !m_queue.isEmpty()) {
        const QString name = m_queue.takeFirst();
        const QUrl url(m_api.pictureUrl(name));
        m_inFlight.insert(name);
        QNetworkRequest request(url);
        request.setTransferTimeout(20000);
        QNetworkReply *reply = m_network->get(request);
        connect(reply, &QNetworkReply::finished, this, [this, reply, name, url]() {
            reply->deleteLater();
            m_inFlight.remove(name);
            const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
            if (reply->error() == QNetworkReply::NoError && status == 200) {
                QByteArray body = reply->readAll();
                // A captive portal answers every request with its own page and a 200: only bytes an image reader
                // recognises are kept.
                QBuffer probe(&body);
                probe.open(QIODevice::ReadOnly);
                if (!QImageReader::imageFormat(&probe).isEmpty()) {
                    QDir().mkpath(pictureFolder());
                    QSaveFile out(pictureFile(name));
                    if (out.open(QIODevice::WriteOnly) && out.write(body) == body.size() && out.commit()) {
                        ++m_pictureRevision;
                        emit picturesChanged();
                    }
                }
            } else if (status == 0 || Api::originDown(status)) {
                // Nothing answered, or the tunnel answered with its own page for a server that is down: asked again later (when another picture lands, or the server is back).
                m_asked.remove(name);
                m_api.noteUnreachable(url);
            }
            fetchNext();
        });
    }
}
