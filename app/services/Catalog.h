#pragma once
#include <QHash>
#include <QObject>
#include <QString>
#include <QStringList>
#include <QVariantList>
#include <QVariantMap>

class ExerciseStore;


// Browsing the catalog (spec §6): the filter panel's options, the chosen filters and text, the tiles they leave, the
// Ctrl+K search, and the exercise the Exercise page shows. It all runs over the copy ExerciseStore keeps, so it works
// with no server (this is the spec's "one filtered query"). Within a facet any chosen value matches; across facets
// all must. The muscle facet matches primary muscles; equipment matches when any of the exercise's equipment is
// chosen. Hidden exercises are never listed or found.
class Catalog : public QObject
{
    Q_OBJECT

    // {"muscle": [{value, count}], "equipment": [...], "measure": [...], "level": [...]}: every word that names a
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

public:
    static const QStringList Facets;

    explicit Catalog(ExerciseStore &store, QObject *parent = nullptr);

    QVariantMap options() const { return m_options; }
    int shownCount() const { return m_shownCount; }
    QVariantList results() const { return m_results; }
    QString text() const { return m_text; }
    bool narrowed() const;
    QVariantMap current() const;
    int currentId() const { return m_currentId; }

    Q_INVOKABLE void toggle(const QString &facet, const QString &value);
    Q_INVOKABLE bool isChosen(const QString &facet, const QString &value) const;
    Q_INVOKABLE void setText(const QString &text);
    // Every filter and the text cleared: the panel's Reset, and a sign-out, so the next person starts fresh.
    Q_INVOKABLE void reset();
    // Ctrl+K: up to `limit` shown exercises whose names hold every word typed, those starting with it first.
    Q_INVOKABLE QVariantList search(const QString &text, int limit = 8) const;
    Q_INVOKABLE void open(int id);

    // Lower case, accents dropped, anything not a letter or digit a space, spaces collapsed.
    static QString folded(const QString &text);
    // Every word typed is in the name, read as written or with its spaces taken out ("pullup" finds "Pull-Up").
    static bool nameMatches(const QString &name, const QString &text);
    static bool matches(const QVariantMap &exercise, const QHash<QString, QStringList> &chosen);

signals:
    void optionsChanged();
    void resultsChanged();
    void currentChanged();

private:
    void rebuild();
    void filter();
    static QVariantMap tileOf(const QVariantMap &exercise);

    ExerciseStore &m_store;
    QHash<QString, QStringList> m_chosen;
    QString m_text;
    QVariantMap m_options;
    int m_shownCount = 0;
    QVariantList m_results;
    int m_currentId = 0;
};
