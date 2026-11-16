#pragma once
#include <QHash>
#include <QList>
#include <QObject>
#include <QString>
#include <QStringList>
#include <QVariantList>
#include <QVariantMap>

#include "api/Api.h"

class ExerciseStore;


// Browsing the catalog (spec §6): the filter panel's options, the chosen filters and text, the tiles they leave, the
// Ctrl+K search, and the exercise the Exercise page shows. It all runs over the copy ExerciseStore keeps, so it works
// with no server (this is the spec's "one filtered query"). Within a facet any chosen value matches; across facets
// all must. The person's own exercises (GET /exercises) join everything below, and a "mine" facet narrows to them.
// The muscle facet matches primary muscles; equipment matches when any of the exercise's equipment is
// chosen. Hidden exercises are never listed or found.
class Catalog : public QObject
{
    Q_OBJECT

    // {"muscle": [{value, count}], "equipment": [...], "measure": [...], "level": [...], "mine": [...]}: every word that names a
    // shown exercise, in Pride's order, counted over the whole shown catalog.
    Q_PROPERTY(QVariantMap options READ options NOTIFY optionsChanged)
    // How many exercises are shown in all, before any filter.
    Q_PROPERTY(int shownCount READ shownCount NOTIFY optionsChanged)
    // The tiles the filters and text leave, in the catalog's order (by name):
    // [{id, name, measure, level, region, primary, equipment, picture}], picture being the first one's name or "".
    Q_PROPERTY(QVariantList results READ results NOTIFY resultsChanged)
    Q_PROPERTY(QString text READ text NOTIFY resultsChanged)
    // Whether any filter or text narrows the tiles.
    Q_PROPERTY(bool narrowed READ narrowed NOTIFY resultsChanged)
    // The exercise the Exercise page shows, looked up again whenever the catalog changes; empty when it has gone.
    Q_PROPERTY(QVariantMap current READ current NOTIFY currentChanged)
    Q_PROPERTY(int currentId READ currentId NOTIFY currentChanged)
    // The person's own exercises, by name, hidden ones included (so a routine can still name them); whether they are
    // being fetched; and why the last fetch failed as a code ("network", "server"), empty when it did not.
    Q_PROPERTY(QVariantList own READ own NOTIFY ownChanged)
    Q_PROPERTY(bool ownLoading READ ownLoading NOTIFY ownChanged)
    Q_PROPERTY(QString ownError READ ownError NOTIFY ownChanged)

public:
    static const QStringList Facets;

    explicit Catalog(ExerciseStore &store, Api &api, QObject *parent = nullptr);

    QVariantMap options() const { return m_options; }
    int shownCount() const { return m_shownCount; }
    QVariantList results() const { return m_results; }
    QString text() const { return m_text; }
    bool narrowed() const;
    QVariantMap current() const;
    int currentId() const { return m_currentId; }
    QVariantList own() const;
    bool ownLoading() const { return m_ownLoading; }
    QString ownError() const { return m_ownError; }

    Q_INVOKABLE void toggle(const QString &facet, const QString &value);
    Q_INVOKABLE bool isChosen(const QString &facet, const QString &value) const;
    Q_INVOKABLE void setText(const QString &text);
    // Every filter and the text cleared: the panel's Reset, and a sign-out, so the next person starts fresh.
    Q_INVOKABLE void reset();
    // Ctrl+K: up to `limit` shown exercises whose names hold every word typed, those starting with it first.
    Q_INVOKABLE QVariantList search(const QString &text, int limit = 8) const;
    Q_INVOKABLE void open(int id);

    // Any exercise by id, the person's own first (hidden ones included), then the catalog's; empty when unknown.
    Q_INVOKABLE QVariantMap exercise(int id) const;
    // The routine editor's picker: shown exercises whose names hold the text. Unless `everything`, only those whose
    // every piece of equipment is in `equipment` or is bodyweight. Tiles as `results`, by name.
    Q_INVOKABLE QVariantList pick(const QString &text, const QStringList &equipment, bool everything,
                                  int limit = 200) const;

    Q_INVOKABLE void loadOwn();
    // `id` 0 or absent creates (POST), otherwise edits (PUT). ownSaved(id) follows the server's answer, or ownFailed.
    Q_INVOKABLE void saveOwn(const QVariantMap &exercise);
    // On ok the exercise leaves `own`, or stays marked removed when routines use it (`hidden`).
    Q_INVOKABLE void removeOwn(int id);
    // A sign-out: the next person has none of these.
    Q_INVOKABLE void resetOwn();

    // Lower case, accents dropped, anything not a letter or digit a space, spaces collapsed.
    static QString folded(const QString &text);
    // Every word typed is in the name, read as written or with its spaces taken out ("pullup" finds "Pull-Up").
    static bool nameMatches(const QString &name, const QString &text);
    static bool matches(const QVariantMap &exercise, const QHash<QString, QStringList> &chosen);

signals:
    void optionsChanged();
    void resultsChanged();
    void currentChanged();
    void ownChanged();
    void ownSaved(int id);
    void ownRemoved(int id, int routinesTouched, bool hidden);
    // Codes as Programs': "invalid" or "limit" with the field at fault, "not_found", "network", "server".
    void ownFailed(const QString &code, const QString &field);

private:
    void rebuild();
    void filter();
    static QVariantMap tileOf(const QVariantMap &exercise);
    static bool before(const QVariantMap &a, const QVariantMap &b);
    // The catalog's exercises and the person's own, together, by name (then id).
    QList<QVariantMap> all() const;
    void takeOwn(const QVariantMap &exercise);
    void ownFailure(const Api::Result &result);

    ExerciseStore &m_store;
    Api &m_api;
    QList<QVariantMap> m_own;
    bool m_ownLoading = false;
    QString m_ownError;
    // Bumped by resetOwn so an answer in flight for the last person is dropped, as Profile does.
    int m_ownGeneration = 0;
    QHash<QString, QStringList> m_chosen;
    QString m_text;
    QVariantMap m_options;
    int m_shownCount = 0;
    QVariantList m_results;
    int m_currentId = 0;
};
