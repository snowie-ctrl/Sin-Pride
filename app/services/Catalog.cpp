#include "services/Catalog.h"

#include <algorithm>

#include "services/ExerciseStore.h"

namespace {

// Each facet's words in the order the panel shows them. The words are server/prideCatalog.py's; the order is
// Pride's (what a beginner has to hand first).
const QHash<QString, QStringList> &wordOrder()
{
    static const QHash<QString, QStringList> order = {
        {"muscle", {"abdominals", "abductors", "adductors", "biceps", "calves", "chest", "forearms", "glutes",
                    "hamstrings", "lats", "lower back", "middle back", "neck", "quadriceps", "shoulders", "traps",
                    "triceps"}},
        {"equipment", {"bodyweight", "dumbbell", "barbell", "kettlebell", "bands", "cable", "machine", "bench",
                       "pull-up bar", "other"}},
        {"measure", {"weight_reps", "reps", "time", "distance_time"}},
        {"level", {"beginner", "intermediate", "expert"}},
    };
    return order;
}

QStringList valuesOf(const QVariantMap &exercise, const QString &facet)
{
    if (facet == QLatin1String("muscle"))
        return exercise.value("primary").toStringList();
    if (facet == QLatin1String("equipment"))
        return exercise.value("equipment").toStringList();
    return {exercise.value(facet).toString()};
}

bool shown(const QVariantMap &exercise)
{
    return !exercise.value("removed").toBool();
}

} // namespace

const QStringList Catalog::Facets = {QStringLiteral("muscle"), QStringLiteral("equipment"), QStringLiteral("measure"),
                                     QStringLiteral("level")};


Catalog::Catalog(ExerciseStore &store, QObject *parent) : QObject(parent), m_store(store)
{
    connect(&m_store, &ExerciseStore::changed, this, &Catalog::rebuild);
    rebuild();
}

void Catalog::rebuild()
{
    QHash<QString, QHash<QString, int>> tally;
    m_shownCount = 0;
    for (const QVariantMap &exercise : m_store.exercises()) {
        if (!shown(exercise))
            continue;
        ++m_shownCount;
        for (const QString &facet : Facets)
            for (const QString &value : valuesOf(exercise, facet))
                ++tally[facet][value];
    }
    QVariantMap options;
    for (const QString &facet : Facets) {
        QVariantList rows;
        for (const QString &value : wordOrder().value(facet))
            if (const int n = tally.value(facet).value(value))
                rows.append(QVariantMap{{"value", value}, {"count", n}});
        options.insert(facet, rows);
    }
    m_options = options;
    emit optionsChanged();
    filter();
    emit currentChanged();
}

bool Catalog::matches(const QVariantMap &exercise, const QHash<QString, QStringList> &chosen)
{
    for (auto it = chosen.constBegin(); it != chosen.constEnd(); ++it) {
        if (it.value().isEmpty())
            continue;
        const QStringList values = valuesOf(exercise, it.key());
        if (std::none_of(values.cbegin(), values.cend(), [&](const QString &v) { return it.value().contains(v); }))
            return false;
    }
    return true;
}

QVariantMap Catalog::tileOf(const QVariantMap &exercise)
{
    const QVariantList pictures = exercise.value("pictures").toList();
    return {{"id", exercise.value("id")}, {"name", exercise.value("name")}, {"measure", exercise.value("measure")},
            {"level", exercise.value("level")}, {"region", exercise.value("region")},
            {"primary", exercise.value("primary")}, {"equipment", exercise.value("equipment")},
            {"picture", pictures.isEmpty() ? QString() : pictures.first().toString()}};
}

void Catalog::filter()
{
    QVariantList results;
    for (const QVariantMap &exercise : m_store.exercises())
        if (shown(exercise) && matches(exercise, m_chosen) && nameMatches(exercise.value("name").toString(), m_text))
            results.append(tileOf(exercise));
    m_results = results;
    emit resultsChanged();
}

bool Catalog::narrowed() const
{
    if (!folded(m_text).isEmpty())
        return true;
    return std::any_of(m_chosen.cbegin(), m_chosen.cend(), [](const QStringList &values) { return !values.isEmpty(); });
}

void Catalog::toggle(const QString &facet, const QString &value)
{
    if (!Facets.contains(facet))
        return;
    QStringList &values = m_chosen[facet];
    if (values.contains(value))
        values.removeAll(value);
    else
        values.append(value);
    filter();
}

bool Catalog::isChosen(const QString &facet, const QString &value) const
{
    return m_chosen.value(facet).contains(value);
}

void Catalog::setText(const QString &text)
{
    if (text == m_text)
        return;
    m_text = text;
    filter();
}

void Catalog::reset()
{
    m_chosen.clear();
    m_text.clear();
    filter();
}

QVariantList Catalog::search(const QString &text, int limit) const
{
    const QString wanted = folded(text);
    if (wanted.isEmpty() || limit <= 0)
        return {};
    QVariantList starting;
    QVariantList containing;
    for (const QVariantMap &exercise : m_store.exercises()) {
        const QString name = exercise.value("name").toString();
        if (!shown(exercise) || !nameMatches(name, text))
            continue;
        (folded(name).startsWith(wanted) ? starting : containing).append(tileOf(exercise));
    }
    starting.append(containing);
    return starting.mid(0, limit);
}

void Catalog::open(int id)
{
    m_currentId = id;
    emit currentChanged();
}

QVariantMap Catalog::current() const
{
    return m_store.exercise(m_currentId);
}

QString Catalog::folded(const QString &text)
{
    const QString decomposed = text.normalized(QString::NormalizationForm_KD);
    QString out;
    out.reserve(decomposed.size());
    for (const QChar ch : decomposed) {
        if (ch.category() == QChar::Mark_NonSpacing)
            continue;
        out.append(ch.isLetterOrNumber() ? ch.toCaseFolded() : QChar(QLatin1Char(' ')));
    }
    return out.simplified();
}

bool Catalog::nameMatches(const QString &name, const QString &text)
{
    const QStringList words = folded(text).split(QLatin1Char(' '), Qt::SkipEmptyParts);
    if (words.isEmpty())
        return true;
    const QString spaced = folded(name);
    QString squashed = spaced;
    squashed.remove(QLatin1Char(' '));
    return std::all_of(words.cbegin(), words.cend(),
                       [&](const QString &word) { return spaced.contains(word) || squashed.contains(word); });
}
