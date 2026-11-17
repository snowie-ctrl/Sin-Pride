#pragma once
#include <QObject>
#include <QString>
#include <QVariantList>
#include <QVariantMap>

#include "api/Api.h"


// Logging workouts (spec §1 Workouts, §6 Log a workout): the routines a workout can follow, the draft a routine
// fills, saving a new workout or an edit (answered with the result card), deleting one, and the history newest
// first. The Log page keeps the sets being typed; this service only fetches and sends, so a refused or unreachable
// save leaves the page's cards as they were and the page sends them again with the same clientId (plan decision
// 26). In memory only, like Programs.
class Workouts : public QObject
{
    Q_OBJECT

    Q_PROPERTY(QVariantList routines READ routines NOTIFY routinesChanged)
    Q_PROPERTY(QString routinesError READ routinesError NOTIFY routinesChanged)
    // The routine a new workout follows (0 for a free one) and its draft (GET /workouts/draft).
    Q_PROPERTY(int routineId READ routineId NOTIFY draftChanged)
    Q_PROPERTY(QVariantMap draft READ draft NOTIFY draftChanged)
    Q_PROPERTY(bool draftLoading READ draftLoading NOTIFY draftChanged)
    Q_PROPERTY(QString draftError READ draftError NOTIFY draftChanged)
    // A past workout open for editing; 0 while a new one is being logged.
    Q_PROPERTY(int editingId READ editingId NOTIFY editingChanged)
    Q_PROPERTY(QVariantMap editing READ editing NOTIFY editingChanged)
    Q_PROPERTY(QString editingError READ editingError NOTIFY editingChanged)
    Q_PROPERTY(QVariantList history READ history NOTIFY historyChanged)
    Q_PROPERTY(bool historyLoading READ historyLoading NOTIFY historyChanged)
    Q_PROPERTY(bool historyLoaded READ historyLoaded NOTIFY historyChanged)
    Q_PROPERTY(QString historyError READ historyError NOTIFY historyChanged)
    // The last save's answer: {workout, crowns, suggestions, nextUp}.
    Q_PROPERTY(QVariantMap result READ result NOTIFY resultChanged)
    // A save or a delete is on its way.
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)

public:
    explicit Workouts(Api &api, QObject *parent = nullptr);

    QVariantList routines() const { return m_routines; }
    QString routinesError() const { return m_routinesError; }
    int routineId() const { return m_routineId; }
    QVariantMap draft() const { return m_draft; }
    bool draftLoading() const { return m_draftLoading; }
    QString draftError() const { return m_draftError; }
    int editingId() const { return m_editingId; }
    QVariantMap editing() const { return m_editing; }
    QString editingError() const { return m_editingError; }
    QVariantList history() const { return m_history; }
    bool historyLoading() const { return m_historyLoading; }
    bool historyLoaded() const { return m_historyLoaded; }
    QString historyError() const { return m_historyError; }
    QVariantMap result() const { return m_result; }
    bool busy() const { return m_busy; }

    Q_INVOKABLE void loadRoutines();
    // A new workout following this routine (its draft is asked for), or a free one (0).
    Q_INVOKABLE void startNew(int routineId);
    // A past workout, for editing.
    Q_INVOKABLE void open(int workoutId);
    // POST while a new workout is being logged, PUT while a past one is open.
    Q_INVOKABLE void save(const QVariantMap &workout);
    Q_INVOKABLE void remove(int workoutId);
    Q_INVOKABLE void loadHistory();
    Q_INVOKABLE QString newClientId() const;
    Q_INVOKABLE void clearResult();
    Q_INVOKABLE void reset();

signals:
    void routinesChanged();
    void draftChanged();
    void editingChanged();
    void historyChanged();
    void resultChanged();
    void busyChanged();
    void saved(int workoutId);
    void removed(int workoutId);
    // what: draft, open, save or remove; code as refusalOf (field only for invalid).
    void failed(const QString &what, const QString &code, const QString &field);

private:
    void setBusy(bool busy);

    Api &m_api;
    QVariantList m_routines;
    QString m_routinesError;
    int m_routineId = 0;
    QVariantMap m_draft;
    bool m_draftLoading = false;
    QString m_draftError;
    int m_editingId = 0;
    QVariantMap m_editing;
    QString m_editingError;
    QVariantList m_history;
    bool m_historyLoading = false;
    bool m_historyLoaded = false;
    QString m_historyError;
    QVariantMap m_result;
    bool m_busy = false;
    int m_generation = 0;
    int m_draftSeq = 0;
    int m_openSeq = 0;
};
