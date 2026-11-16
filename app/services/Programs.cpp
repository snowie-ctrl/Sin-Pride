#include "services/Programs.h"

#include <QJsonArray>
#include <QUrlQuery>


Programs::Programs(Api &api, QObject *parent) : QObject(parent), m_api(api) {}

QString Programs::codeOf(const Api::Result &result)
{
    return refusalOf(result);
}

QVariantMap Programs::currentRoutine() const
{
    for (const QVariant &routine : m_current.value("routines").toList())
        if (routine.toMap().value("id").toInt() == m_routineId)
            return routine.toMap();
    return {};
}

void Programs::noteGone(const QString &what)
{
    m_goneNotice = what;
    emit goneNoticeChanged();
    emit gone(what);
}

void Programs::clearGoneNotice()
{
    if (m_goneNotice.isEmpty())
        return;
    m_goneNotice.clear();
    emit goneNoticeChanged();
}

void Programs::takeProgram(const QJsonObject &data)
{
    m_current = data.toVariantMap();
    emit currentChanged();
}

void Programs::write(const QString &what, const QString &method, const QString &path, const QJsonObject &body,
                     Answer answer, int listId)
{
    const int generation = m_generation;
    const int openSeq = m_openSeq;
    auto done = [this, generation, openSeq, what, answer, listId](const Api::Result &result) {
        if (generation != m_generation)
            return;
        if (!result.ok) {
            const QString code = codeOf(result);
            if (code == QLatin1String("not_found") && what != QLatin1String("adopted")) {
                if (answer == Answer::Program && currentId()) {
                    // A 404 on a routine or an item may mean only that one is gone, not the whole program: ask for
                    // the program again, and only a 404 on that closes it and says it is gone.
                    fetch(currentId(), what);
                    return;
                }
                // A list write names the program it is about; losing some other program must not close the open one.
                const bool listWrite = answer == Answer::List;
                if (!listWrite || listId == currentId()) {
                    m_current.clear();
                    m_routineId = 0;
                    emit currentChanged();
                }
                noteGone(what);
                loadList();
                loadToday();
                return;
            }
            emit failed(what, code, code == QLatin1String("invalid") || code == QLatin1String("limit")
                                        ? result.object.value("field").toString() : QString());
            return;
        }
        int id = 0;
        if (answer == Answer::Program) {
            const QJsonObject data = result.object.value("data").toObject();
            // Another program was opened while this write was out: its answer is about a program that is no longer
            // the one on screen, so it must not replace the newer one.
            if (openSeq == m_openSeq || data.value("id").toInt() == m_openingId)
                takeProgram(data);
            id = data.value("id").toInt();
            loadList();
        } else {
            m_programs = result.object.value("data").toArray().toVariantList();
            emit programsChanged();
            id = listId;
            // Only removing closes the program; activating it leaves it open, but its `active` flag is now stale.
            if (what == QLatin1String("removed") && listId && listId == currentId()) {
                m_current.clear();
                m_routineId = 0;
                emit currentChanged();
            } else if (currentId()) {
                open(currentId());
            }
        }
        loadToday();
        emit saved(what, id);
    };
    if (method == QLatin1String("POST"))
        m_api.post(path, body, done);
    else if (method == QLatin1String("PUT"))
        m_api.put(path, body, done);
    else
        m_api.del(path, done);
}

void Programs::loadList()
{
    const int generation = m_generation;
    m_listLoading = true;
    emit programsChanged();
    m_api.get(QStringLiteral("/programs"), QUrlQuery(), [this, generation](const Api::Result &result) {
        if (generation != m_generation)
            return;
        m_listLoading = false;
        m_listError = result.ok ? QString() : failureOf(result);
        if (result.ok)
            m_programs = result.object.value("data").toArray().toVariantList();
        emit programsChanged();
    });
}

void Programs::open(int programId)
{
    fetch(programId, QString());
}

void Programs::fetch(int programId, const QString &afterGone)
{
    const int generation = m_generation;
    // Only the latest ask may answer: two quick opens can come back in either order, and the earlier one's late
    // answer must not replace the later one's program.
    const int seq = ++m_openSeq;
    m_openingId = programId;
    m_api.get(QStringLiteral("/programs/%1").arg(programId), QUrlQuery(), [this, generation, seq, programId, afterGone](const Api::Result &result) {
        if (generation != m_generation || seq != m_openSeq)
            return;
        if (result.httpStatus == 404) {
            if (programId == currentId()) {
                m_current.clear();
                m_routineId = 0;
                emit currentChanged();
            }
            noteGone(QStringLiteral("program"));
            loadList();
            if (!afterGone.isEmpty())
                loadToday();
            return;
        }
        if (!result.ok) {
            emit failed(afterGone.isEmpty() ? QStringLiteral("program") : afterGone, failureOf(result), QString());
            return;
        }
        if (result.object.value("data").toObject().value("id").toInt() != currentId())
            m_routineId = 0;
        takeProgram(result.object.value("data").toObject());
        if (!afterGone.isEmpty()) {
            // The program is still there, so what the write named is what is gone; the fresh copy is already shown.
            emit failed(afterGone, QStringLiteral("not_found"), QString());
            loadList();
            loadToday();
        }
    });
}

void Programs::openRoutine(int routineId)
{
    m_routineId = routineId;
    emit currentChanged();
}

void Programs::create(const QString &title)
{
    m_routineId = 0;
    write(QStringLiteral("program"), QStringLiteral("POST"), QStringLiteral("/programs"), {{"title", title}}, Answer::Program);
}

void Programs::rename(int id, const QString &title)
{
    write(QStringLiteral("program"), QStringLiteral("PUT"), QStringLiteral("/programs/%1").arg(id), {{"title", title}},
          Answer::Program);
}

void Programs::duplicate(int id)
{
    m_routineId = 0;
    write(QStringLiteral("program"), QStringLiteral("POST"), QStringLiteral("/programs/%1/duplicate").arg(id), {},
          Answer::Program);
}

void Programs::remove(int id)
{
    write(QStringLiteral("removed"), QStringLiteral("DELETE"), QStringLiteral("/programs/%1").arg(id), {}, Answer::List, id);
}

void Programs::activate(int id)
{
    write(QStringLiteral("activated"), QStringLiteral("POST"), QStringLiteral("/programs/%1/activate").arg(id), {},
          Answer::List, id);
}

void Programs::setDays(int id, const QVariantList &days)
{
    write(QStringLiteral("days"), QStringLiteral("PUT"), QStringLiteral("/programs/%1/days").arg(id),
          {{"days", QJsonArray::fromVariantList(days)}}, Answer::Program);
}

void Programs::addRoutine(int programId, const QString &title)
{
    write(QStringLiteral("routine"), QStringLiteral("POST"), QStringLiteral("/routines"),
          {{"programId", programId}, {"title", title}}, Answer::Program);
}

void Programs::renameRoutine(int id, const QString &title)
{
    write(QStringLiteral("routine"), QStringLiteral("PUT"), QStringLiteral("/routines/%1").arg(id), {{"title", title}},
          Answer::Program);
}

void Programs::removeRoutine(int id)
{
    if (id == m_routineId)
        m_routineId = 0;
    write(QStringLiteral("routine"), QStringLiteral("DELETE"), QStringLiteral("/routines/%1").arg(id), {}, Answer::Program);
}

void Programs::reorderRoutines(int programId, const QVariantList &ids)
{
    write(QStringLiteral("order"), QStringLiteral("POST"), QStringLiteral("/routines/reorder"),
          {{"programId", programId}, {"order", QJsonArray::fromVariantList(ids)}}, Answer::Program);
}

void Programs::addItem(int routineId, int exerciseId)
{
    write(QStringLiteral("item"), QStringLiteral("POST"), QStringLiteral("/routine-items"),
          {{"routineId", routineId}, {"exerciseId", exerciseId}}, Answer::Program);
}

void Programs::updateItem(int itemId, const QVariantMap &targets)
{
    write(QStringLiteral("item"), QStringLiteral("PUT"), QStringLiteral("/routine-items/%1").arg(itemId),
          QJsonObject::fromVariantMap(targets), Answer::Program);
}

void Programs::removeItem(int itemId)
{
    write(QStringLiteral("item"), QStringLiteral("DELETE"), QStringLiteral("/routine-items/%1").arg(itemId), {},
          Answer::Program);
}

void Programs::reorderItems(int routineId, const QVariantList &ids)
{
    write(QStringLiteral("order"), QStringLiteral("POST"), QStringLiteral("/routine-items/reorder"),
          {{"routineId", routineId}, {"order", QJsonArray::fromVariantList(ids)}}, Answer::Program);
}

void Programs::loadToday()
{
    const int generation = m_generation;
    m_todayLoading = true;
    emit todayChanged();
    QUrlQuery query;
    query.addQueryItem(QStringLiteral("date"), todayDate());
    m_api.get(QStringLiteral("/today"), query, [this, generation](const Api::Result &result) {
        if (generation != m_generation)
            return;
        m_todayLoading = false;
        m_todayError = result.ok ? QString() : failureOf(result);
        if (result.ok)
            m_today = result.object.value("data").toObject().toVariantMap();
        emit todayChanged();
    });
}

void Programs::loadStarters()
{
    const int generation = m_generation;
    m_startersLoading = true;
    emit startersChanged();
    m_api.get(QStringLiteral("/starters"), QUrlQuery(), [this, generation](const Api::Result &result) {
        if (generation != m_generation)
            return;
        m_startersLoading = false;
        m_startersError = result.ok ? QString() : failureOf(result);
        if (result.ok)
            m_starters = result.object.value("data").toArray().toVariantList();
        emit startersChanged();
    });
}

void Programs::adopt(const QString &key)
{
    m_routineId = 0;
    write(QStringLiteral("adopted"), QStringLiteral("POST"), QStringLiteral("/starters/%1/adopt").arg(key), {},
          Answer::Program);
}

void Programs::reset()
{
    ++m_generation;
    m_programs.clear();
    m_current.clear();
    m_routineId = 0;
    m_today.clear();
    m_starters.clear();
    m_listLoading = m_todayLoading = m_startersLoading = false;
    m_goneNotice.clear();
    m_listError.clear();
    m_todayError.clear();
    m_startersError.clear();
    emit programsChanged();
    emit currentChanged();
    emit todayChanged();
    emit startersChanged();
}
