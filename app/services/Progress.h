#pragma once
#include <QObject>
#include <QString>
#include <QVariantList>
#include <QVariantMap>

#include "api/Api.h"


// Progress (spec §1 Progress, §6 Progress and Today): the records of every exercise logged, one exercise's chart
// series (the Progress page's chosen exercise, or the Exercise page's), and taking or dismissing a suggestion. What
// a decision changes elsewhere (Today, an open program) is wiring's to ask for again (Wiring.cpp).
class Progress : public QObject
{
    Q_OBJECT

    Q_PROPERTY(QVariantList records READ records NOTIFY recordsChanged)
    Q_PROPERTY(bool recordsLoading READ recordsLoading NOTIFY recordsChanged)
    Q_PROPERTY(bool recordsLoaded READ recordsLoaded NOTIFY recordsChanged)
    Q_PROPERTY(QString recordsError READ recordsError NOTIFY recordsChanged)
    Q_PROPERTY(int seriesId READ seriesId NOTIFY seriesChanged)
    Q_PROPERTY(QVariantMap series READ series NOTIFY seriesChanged)
    Q_PROPERTY(bool seriesLoading READ seriesLoading NOTIFY seriesChanged)
    Q_PROPERTY(QString seriesError READ seriesError NOTIFY seriesChanged)

public:
    explicit Progress(Api &api, QObject *parent = nullptr);

    QVariantList records() const { return m_records; }
    bool recordsLoading() const { return m_recordsLoading; }
    bool recordsLoaded() const { return m_recordsLoaded; }
    QString recordsError() const { return m_recordsError; }
    int seriesId() const { return m_seriesId; }
    QVariantMap series() const { return m_series; }
    bool seriesLoading() const { return m_seriesLoading; }
    QString seriesError() const { return m_seriesError; }

    Q_INVOKABLE void loadRecords();
    Q_INVOKABLE void loadSeries(int exerciseId);
    Q_INVOKABLE void accept(int suggestionId);
    Q_INVOKABLE void dismiss(int suggestionId);
    Q_INVOKABLE void reset();

signals:
    void recordsChanged();
    void seriesChanged();
    // what: accepted or dismissed; programId: the program whose routine took the target (0 for a dismissal).
    void decided(int suggestionId, const QString &what, int programId);
    // what: accept, dismiss, records or series; code as refusalOf, plus "closed" for a suggestion no longer open.
    void failed(const QString &what, const QString &code);

private:
    void decide(int suggestionId, const QString &verb, const QString &what);

    Api &m_api;
    QVariantList m_records;
    bool m_recordsLoading = false;
    bool m_recordsLoaded = false;
    QString m_recordsError;
    int m_seriesId = 0;
    QVariantMap m_series;
    bool m_seriesLoading = false;
    QString m_seriesError;
    int m_generation = 0;
    int m_seriesSeq = 0;
};
