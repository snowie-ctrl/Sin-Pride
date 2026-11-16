#include "services/Profile.h"

#include <QJsonObject>


Profile::Profile(Api &api, QObject *parent) : QObject(parent), m_api(api) {}

void Profile::take(const QJsonObject &data)
{
    m_profile = data.toVariantMap();
    m_error.clear();
    emit changed();
    if (m_profile.value("introState").toString() == QLatin1String("pending"))
        emit introPending();
}

void Profile::load()
{
    const int generation = m_generation;
    m_loading = true;
    emit changed();
    m_api.get(QStringLiteral("/profile"), QUrlQuery(), [this, generation](const Api::Result &result) {
        if (generation != m_generation)
            return;
        m_loading = false;
        if (!result.ok) {
            m_error = failureOf(result);
            emit changed();
            return;
        }
        take(result.object.value("data").toObject());
    });
}

void Profile::save(const QVariantMap &changes)
{
    const int generation = m_generation;
    m_api.put(QStringLiteral("/profile"), QJsonObject::fromVariantMap(changes),
              [this, generation](const Api::Result &result) {
        if (generation != m_generation)
            return;
        if (!result.ok) {
            const bool refused = result.httpStatus == 400;
            emit failed(refused ? QStringLiteral("invalid") : failureOf(result),
                        refused ? result.object.value("field").toString() : QString());
            return;
        }
        take(result.object.value("data").toObject());
        emit saved();
    });
}

void Profile::reset()
{
    ++m_generation;
    m_profile.clear();
    m_loading = false;
    m_error.clear();
    emit changed();
}
