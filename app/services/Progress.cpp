#include "services/Progress.h"

#include <QJsonArray>
#include <QJsonObject>
#include <QUrlQuery>


Progress::Progress(Api &api, QObject *parent) : QObject(parent), m_api(api) {}

void Progress::loadRecords()
{
    const int generation = m_generation;
    m_recordsLoading = true;
    emit recordsChanged();
    m_api.get(QStringLiteral("/records"), QUrlQuery(), [this, generation](const Api::Result &result) {
        if (generation != m_generation)
            return;
        m_recordsLoading = false;
        m_recordsError = result.ok ? QString() : failureOf(result);
        if (result.ok) {
            m_records = result.object.value("data").toArray().toVariantList();
            m_recordsLoaded = true;
        } else {
            emit failed(QStringLiteral("records"), m_recordsError);
        }
        emit recordsChanged();
    });
}

void Progress::loadSeries(int exerciseId)
{
    const int generation = m_generation;
    // Only the latest ask answers: picking two exercises quickly must end on the second.
    const int seq = ++m_seriesSeq;
    if (exerciseId != m_seriesId)
        m_series.clear();
    m_seriesId = exerciseId;
    m_seriesLoading = true;
    m_seriesError.clear();
    emit seriesChanged();
    m_api.get(QStringLiteral("/progress/%1").arg(exerciseId), QUrlQuery(), [this, generation, seq](const Api::Result &result) {
        if (generation != m_generation || seq != m_seriesSeq)
            return;
        m_seriesLoading = false;
        if (result.ok) {
            m_series = result.object.value("data").toObject().toVariantMap();
        } else {
            m_seriesError = refusalOf(result);
            emit failed(QStringLiteral("series"), m_seriesError);
        }
        emit seriesChanged();
    });
}

void Progress::decide(int suggestionId, const QString &verb, const QString &what)
{
    const int generation = m_generation;
    m_api.post(QStringLiteral("/suggestions/%1/%2").arg(suggestionId).arg(verb), QJsonObject(),
               [this, generation, suggestionId, verb, what](const Api::Result &result) {
        if (generation != m_generation)
            return;
        if (!result.ok) {
            const bool closed = result.httpStatus == 409
                                && result.object.value("status").toString() == QLatin1String("closed");
            emit failed(verb, closed ? QStringLiteral("closed") : refusalOf(result));
            return;
        }
        emit decided(suggestionId, what, result.object.value("data").toObject().value("programId").toInt());
    });
}

void Progress::accept(int suggestionId)
{
    decide(suggestionId, QStringLiteral("accept"), QStringLiteral("accepted"));
}

void Progress::dismiss(int suggestionId)
{
    decide(suggestionId, QStringLiteral("dismiss"), QStringLiteral("dismissed"));
}

void Progress::reset()
{
    ++m_generation;
    m_records.clear();
    m_recordsLoading = false;
    m_recordsLoaded = false;
    m_recordsError.clear();
    m_seriesId = 0;
    m_series.clear();
    m_seriesLoading = false;
    m_seriesError.clear();
    emit recordsChanged();
    emit seriesChanged();
}
