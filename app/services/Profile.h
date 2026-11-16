#pragma once
#include <QObject>
#include <QString>
#include <QVariantMap>

#include "api/Api.h"


// The person's profile (spec §3): units, goal, days a week, the two increments, week start, the intro's state and
// their equipment. Kept in memory for the session (plan decision 24): loaded when someone signs in, cleared when they
// sign out. save() sends only what changed and takes the server's answer whole, so a switch of units comes back with
// the increments the server reset (plan decision 4).
class Profile : public QObject
{
    Q_OBJECT

    // GET /profile's data; empty until the first load answers.
    Q_PROPERTY(QVariantMap profile READ profile NOTIFY changed)
    Q_PROPERTY(bool loaded READ loaded NOTIFY changed)
    Q_PROPERTY(bool loading READ loading NOTIFY changed)
    // Why the last load failed, as a code (network, server); empty after one that worked.
    Q_PROPERTY(QString error READ error NOTIFY changed)

public:
    explicit Profile(Api &api, QObject *parent = nullptr);

    QVariantMap profile() const { return m_profile; }
    bool loaded() const { return !m_profile.isEmpty(); }
    bool loading() const { return m_loading; }
    QString error() const { return m_error; }

    Q_INVOKABLE void load();
    Q_INVOKABLE void save(const QVariantMap &changes);
    // Signed out: nothing of this person is kept, and an answer still on its way for them is dropped.
    Q_INVOKABLE void reset();

signals:
    void changed();
    void saved();
    // code: network, server, or invalid with the field the server named.
    void failed(const QString &code, const QString &field);
    // A load or save found the intro still pending (plan decision 6): the app shows it.
    void introPending();

private:
    void take(const QJsonObject &data);

    Api &m_api;
    QVariantMap m_profile;
    bool m_loading = false;
    QString m_error;
    int m_generation = 0;
};
