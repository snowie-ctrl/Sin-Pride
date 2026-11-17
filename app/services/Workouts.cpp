#include "services/Workouts.h"

#include <QJsonArray>
#include <QJsonObject>
#include <QUrlQuery>
#include <QUuid>


Workouts::Workouts(Api &api, QObject *parent) : QObject(parent), m_api(api) {}

void Workouts::setBusy(bool busy)
{
    if (busy == m_busy)
        return;
    m_busy = busy;
    emit busyChanged();
}

QString Workouts::newClientId() const
{
    return QUuid::createUuid().toString(QUuid::WithoutBraces).toLower();
}

void Workouts::loadRoutines()
{
    const int generation = m_generation;
    m_api.get(QStringLiteral("/routines"), QUrlQuery(), [this, generation](const Api::Result &result) {
        if (generation != m_generation)
            return;
        m_routinesError = result.ok ? QString() : failureOf(result);
        if (result.ok)
            m_routines = result.object.value("data").toArray().toVariantList();
        emit routinesChanged();
    });
}

void Workouts::startNew(int routineId)
{
    // A new log replaces whatever was open; only the latest draft asked for may answer.
    const int seq = ++m_draftSeq;
    ++m_openSeq;
    m_editingId = 0;
    m_editing.clear();
    m_editingError.clear();
    emit editingChanged();
    m_routineId = routineId;
    m_draft.clear();
    m_draftError.clear();
    m_draftLoading = routineId > 0;
    emit draftChanged();
    if (routineId <= 0)
        return;
    const int generation = m_generation;
    QUrlQuery query;
    query.addQueryItem(QStringLiteral("routineId"), QString::number(routineId));
    m_api.get(QStringLiteral("/workouts/draft"), query, [this, generation, seq](const Api::Result &result) {
        if (generation != m_generation || seq != m_draftSeq)
            return;
        m_draftLoading = false;
        if (result.ok) {
            m_draft = result.object.value("data").toObject().toVariantMap();
        } else {
            m_draftError = refusalOf(result);
            emit failed(QStringLiteral("draft"), m_draftError, QString());
        }
        emit draftChanged();
    });
}

void Workouts::open(int workoutId)
{
    const int seq = ++m_openSeq;
    ++m_draftSeq;
    m_editingId = workoutId;
    m_editing.clear();
    m_editingError.clear();
    emit editingChanged();
    const int generation = m_generation;
    m_api.get(QStringLiteral("/workouts/%1").arg(workoutId), QUrlQuery(), [this, generation, seq](const Api::Result &result) {
        if (generation != m_generation || seq != m_openSeq)
            return;
        if (result.ok) {
            m_editing = result.object.value("data").toObject().toVariantMap();
        } else {
            m_editingError = refusalOf(result);
            emit failed(QStringLiteral("open"), m_editingError, QString());
        }
        emit editingChanged();
    });
}

void Workouts::save(const QVariantMap &workout)
{
    const int generation = m_generation;
    const int editing = m_editingId;
    setBusy(true);
    auto done = [this, generation, editing](const Api::Result &result) {
        if (generation != m_generation)
            return;
        setBusy(false);
        if (!result.ok) {
            const QString code = refusalOf(result);
            emit failed(QStringLiteral("save"), code,
                        code == QLatin1String("invalid") ? result.object.value("field").toString() : QString());
            return;
        }
        m_result = result.object.value("data").toObject().toVariantMap();
        emit resultChanged();
        const int id = m_result.value("workout").toMap().value("id").toInt();
        if (editing && editing == m_editingId) {
            m_editing = m_result.value("workout").toMap();
            emit editingChanged();
        }
        emit saved(id);
    };
    const QJsonObject body = QJsonObject::fromVariantMap(workout);
    if (editing)
        m_api.put(QStringLiteral("/workouts/%1").arg(editing), body, done);
    else
        m_api.post(QStringLiteral("/workouts"), body, done);
}

void Workouts::remove(int workoutId)
{
    const int generation = m_generation;
    setBusy(true);
    m_api.del(QStringLiteral("/workouts/%1").arg(workoutId), [this, generation, workoutId](const Api::Result &result) {
        if (generation != m_generation)
            return;
        setBusy(false);
        if (!result.ok) {
            emit failed(QStringLiteral("remove"), refusalOf(result), QString());
            return;
        }
        if (workoutId == m_editingId) {
            m_editingId = 0;
            m_editing.clear();
            emit editingChanged();
        }
        emit removed(workoutId);
    });
}

void Workouts::loadHistory()
{
    const int generation = m_generation;
    m_historyLoading = true;
    emit historyChanged();
    m_api.get(QStringLiteral("/workouts"), QUrlQuery(), [this, generation](const Api::Result &result) {
        if (generation != m_generation)
            return;
        m_historyLoading = false;
        m_historyError = result.ok ? QString() : failureOf(result);
        if (result.ok) {
            m_history = result.object.value("data").toArray().toVariantList();
            m_historyLoaded = true;
        }
        emit historyChanged();
    });
}

void Workouts::clearResult()
{
    if (m_result.isEmpty())
        return;
    m_result.clear();
    emit resultChanged();
}

void Workouts::reset()
{
    ++m_generation;
    m_routines.clear();
    m_routinesError.clear();
    m_routineId = 0;
    m_draft.clear();
    m_draftLoading = false;
    m_draftError.clear();
    m_editingId = 0;
    m_editing.clear();
    m_editingError.clear();
    m_history.clear();
    m_historyLoading = false;
    m_historyLoaded = false;
    m_historyError.clear();
    m_result.clear();
    m_busy = false;
    emit routinesChanged();
    emit draftChanged();
    emit editingChanged();
    emit historyChanged();
    emit resultChanged();
    emit busyChanged();
}
