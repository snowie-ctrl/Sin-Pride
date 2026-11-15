#pragma once
#include <QHash>
#include <QList>
#include <QObject>
#include <QSet>
#include <QString>
#include <QStringList>
#include <QVariantMap>

#include "api/Api.h"

class QNetworkAccessManager;


// The exercise catalog kept on this device (spec §1, §8), so the Catalog and Exercise pages work with no server.
// <root>/catalog/catalog.json holds the whole catalog as GET /catalog last gave it, and <root>/catalog/pictures/ the
// pictures already looked at, under the server's names (each the hash of its content, so a name never changes
// meaning and a kept picture never goes stale). The catalog is the same for everyone, so it belongs to the device,
// not to an account, and stays after a sign-out.
//
// refresh() asks with the version kept here: "unchanged" costs nothing; anything else replaces the copy whole and
// deletes the pictures no exercise names any more. A failed refresh keeps the copy, and a copy that does not read
// whole is no copy. A picture is fetched the first time something asks for it, a few at a time, and kept only if it
// reads as an image.
class ExerciseStore : public QObject
{
    Q_OBJECT

    // Bumped whenever the catalog changes, so bindings that call exercise() are evaluated again.
    Q_PROPERTY(int revision READ revision NOTIFY changed)
    Q_PROPERTY(int count READ count NOTIFY changed)
    // Bumped whenever a picture lands (or may be asked for again), so bindings that call pictureUrl() are evaluated again.
    Q_PROPERTY(int pictureRevision READ pictureRevision NOTIFY picturesChanged)
    Q_PROPERTY(bool loading READ loading NOTIFY loadingChanged)
    // Why the last refresh failed, in the server's words; empty after one that worked.
    Q_PROPERTY(QString error READ error NOTIFY loadingChanged)

public:
    static constexpr int Parallel = 4;

    ExerciseStore(Api &api, const QString &root, QObject *parent = nullptr);

    int revision() const { return m_revision; }
    int count() const { return int(m_exercises.size()); }
    int pictureRevision() const { return m_pictureRevision; }
    bool loading() const { return m_loading; }
    QString error() const { return m_error; }
    QString version() const { return m_version; }
    // Every exercise in the server's order (by name), hidden ones included, so old workouts can still name theirs.
    const QList<QVariantMap> &exercises() const { return m_exercises; }

    Q_INVOKABLE QVariantMap exercise(int id) const;
    Q_INVOKABLE void refresh();
    // A file URL for a picture kept on disk. Otherwise empty, and the picture is asked for: once a session if the
    // server refused it (again after a new sign-in), and again later if nothing answered.
    Q_INVOKABLE QString pictureUrl(const QString &name);

    static bool validPictureName(const QString &name);

signals:
    void changed();
    void picturesChanged();
    void loadingChanged();

private:
    void load();
    bool adopt(const QJsonObject &data);
    void save() const;
    void prunePictures();
    void fetchNext();
    QString catalogFile() const;
    QString pictureFolder() const;
    QString pictureFile(const QString &name) const;

    Api &m_api;
    QString m_root;
    QNetworkAccessManager *m_network;
    QString m_version;
    QList<QVariantMap> m_exercises;
    QHash<int, int> m_index;
    int m_revision = 0;
    int m_pictureRevision = 0;
    bool m_loading = false;
    bool m_refreshAgain = false;
    QString m_error;
    QStringList m_queue;
    QSet<QString> m_inFlight;
    // Asked for this session (queued, in flight, or refused); a name with no answer leaves it to be asked again.
    QSet<QString> m_asked;
};
