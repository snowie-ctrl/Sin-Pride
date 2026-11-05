// Copied from Gluttony app/services/AccountStore.h at c1ed705; no saved recipes: an offline start needs only the account's folder, since Pride's catalog belongs to the device.
#pragma once
#include <QJsonObject>
#include <QObject>
#include <QString>
#include <QVariantMap>


// Everything this device keeps for one account, under <data>/accounts/<UID>/: account.json (UID and username, never a
// token) now, and what later milestones keep per person. <data>/accounts/last.json names the account signed in last,
// so a start with no server can open it offline; the catalog its pages read belongs to the device (ExerciseStore). No
// networking happens here.
class AccountStore : public QObject
{
    Q_OBJECT

public:
    explicit AccountStore(const QString &root, QObject *parent = nullptr);

    // -1 and empty paths while no account is open.
    int uid() const { return m_uid; }
    QString dir() const;
    QString file(const QString &name) const;

    // Signing in: the account's folder, and who it belongs to. Opening the account already open (a new
    // username) is not a change of account.
    void open(int uid, const QString &username);
    // Signed out without deleting (an ended session, a forgotten device).
    void close();
    // Signing out: everyone is told first, then the folder goes.
    void wipe();
    // Signing out of an account already closed: its folder goes too.
    void wipeAccount(int uid);

    // A sign-out the server could not be told about, kept outside the account's folder so it outlives the wipe.
    // While it is there the device never signs in by itself; Session tells the server first.
    int pendingLogout() const { return m_pendingLogout; }
    void setPendingLogout(int uid);
    void clearPendingLogout();
    // The server has forgotten this device: no start without a server opens an account offline.
    void forgetLast();

    // The account signed in last, {UID, username}, while its folder is still on this device; empty otherwise.
    QVariantMap offlineAccount() const;

    // Written whole or not at all, so a crash never leaves half a file.
    static bool writeJson(const QString &path, const QJsonObject &object);
    static QJsonObject readJson(const QString &path);

signals:
    // The open account changed (signed in, out, or wiped): everything kept per account is looked for again.
    void changed();
    // An account's folder was deleted (a sign-out), naming it: what belongs to that account goes too, unlike a
    // folder that is only closed (an ended session), whose account may sign in again.
    void wiped(int uid);

private:
    void removeAccount(int uid);
    QString accountsDir() const;

    QString m_root;
    int m_uid = -1;
    int m_pendingLogout = -1;
};
