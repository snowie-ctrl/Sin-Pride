#pragma once
#include <QDate>
#include <QObject>
#include <QString>
#include <QVariantList>
#include <QVariantMap>

#include "api/Api.h"


// A person's programs (spec §1 Programs, §6): the list, the program open on the Programs page and the routine open in
// the editor, every write to them, Today (next up, the planned day, the week) and the starter programs. Every write
// to a program answers with the whole program (plan decision 15), which replaces the open copy; the list and Today
// are then asked for again so every page agrees. In memory only (plan decision 24). Something deleted on another
// device answers 404: the open copy is closed, the list reloaded, and gone() lets the page say so.
class Programs : public QObject
{
    Q_OBJECT

    Q_PROPERTY(QVariantList programs READ programs NOTIFY programsChanged)
    Q_PROPERTY(bool listLoading READ listLoading NOTIFY programsChanged)
    Q_PROPERTY(QString listError READ listError NOTIFY programsChanged)
    Q_PROPERTY(QVariantMap current READ current NOTIFY currentChanged)
    Q_PROPERTY(int currentId READ currentId NOTIFY currentChanged)
    Q_PROPERTY(QVariantMap currentRoutine READ currentRoutine NOTIFY currentChanged)
    Q_PROPERTY(int currentRoutineId READ currentRoutineId NOTIFY currentChanged)
    Q_PROPERTY(QVariantMap today READ today NOTIFY todayChanged)
    Q_PROPERTY(bool todayLoading READ todayLoading NOTIFY todayChanged)
    Q_PROPERTY(QString todayError READ todayError NOTIFY todayChanged)
    // The date Today was asked for (YYYY-MM-DD), for the page's "planned for …" words.
    Q_PROPERTY(QString todayDate READ todayDate NOTIFY todayChanged)
    Q_PROPERTY(QVariantList starters READ starters NOTIFY startersChanged)
    Q_PROPERTY(bool startersLoading READ startersLoading NOTIFY startersChanged)
    Q_PROPERTY(QString startersError READ startersError NOTIFY startersChanged)

public:
    explicit Programs(Api &api, QObject *parent = nullptr);

    QVariantList programs() const { return m_programs; }
    bool listLoading() const { return m_listLoading; }
    QString listError() const { return m_listError; }
    QVariantMap current() const { return m_current; }
    int currentId() const { return m_current.value("id").toInt(); }
    QVariantMap currentRoutine() const;
    int currentRoutineId() const { return currentRoutine().value("id").toInt(); }
    QVariantMap today() const { return m_today; }
    bool todayLoading() const { return m_todayLoading; }
    QString todayError() const { return m_todayError; }
    QString todayDate() const { return dateToday().toString(Qt::ISODate); }
    QVariantList starters() const { return m_starters; }
    bool startersLoading() const { return m_startersLoading; }
    QString startersError() const { return m_startersError; }

    // Tests fix the date; otherwise it is this device's own date at each ask (plan decision 21).
    void setToday(const QDate &day) { m_fixedToday = day; }

    Q_INVOKABLE void loadList();
    Q_INVOKABLE void open(int programId);
    Q_INVOKABLE void openRoutine(int routineId);
    Q_INVOKABLE void create(const QString &title);
    Q_INVOKABLE void rename(int programId, const QString &title);
    Q_INVOKABLE void duplicate(int programId);
    Q_INVOKABLE void remove(int programId);
    Q_INVOKABLE void activate(int programId);
    Q_INVOKABLE void setDays(int programId, const QVariantList &days);
    Q_INVOKABLE void addRoutine(int programId, const QString &title);
    Q_INVOKABLE void renameRoutine(int routineId, const QString &title);
    Q_INVOKABLE void removeRoutine(int routineId);
    Q_INVOKABLE void reorderRoutines(int programId, const QVariantList &ids);
    Q_INVOKABLE void addItem(int routineId, int exerciseId);
    Q_INVOKABLE void updateItem(int itemId, const QVariantMap &targets);
    Q_INVOKABLE void removeItem(int itemId);
    Q_INVOKABLE void reorderItems(int routineId, const QVariantList &ids);
    Q_INVOKABLE void loadToday();
    Q_INVOKABLE void loadStarters();
    // The key goes into the request path, so call this only with a key taken from starters() (plain words of
    // letters, which the starter files keep); never with text a person typed.
    Q_INVOKABLE void adopt(const QString &key);
    Q_INVOKABLE void reset();

signals:
    void programsChanged();
    void currentChanged();
    void todayChanged();
    void startersChanged();
    void saved(const QString &what, int id);
    void failed(const QString &what, const QString &code, const QString &field);
    void gone(const QString &what);

private:
    enum class Answer { Program, List };
    // Sends one write; its answer replaces the open program (or the list), then the list and Today are asked for
    // again. A 404 is gone(); any other refusal is failed() with its code and field.
    void write(const QString &what, const QString &method, const QString &path, const QJsonObject &body, Answer answer,
               int listId = 0);
    void takeProgram(const QJsonObject &data);
    QDate dateToday() const { return m_fixedToday.isValid() ? m_fixedToday : QDate::currentDate(); }
    static QString codeOf(const Api::Result &result);

    Api &m_api;
    QVariantList m_programs;
    bool m_listLoading = false;
    QString m_listError;
    QVariantMap m_current;
    int m_routineId = 0;
    QVariantMap m_today;
    bool m_todayLoading = false;
    QString m_todayError;
    QVariantList m_starters;
    bool m_startersLoading = false;
    QString m_startersError;
    QDate m_fixedToday;
    int m_generation = 0;
};
