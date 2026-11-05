// Copied from Gluttony app/assets/Preferences.h at c1ed705; Pride's look ("Superbia") replaces Gula, goldColor is
// new, and units are gone (Pride keeps them on the server, in the profile).
#pragma once
#include <QColor>
#include <QObject>
#include <QStringList>
#include <QTimer>
#include <QVariantMap>


// Every look and per-device choice, saved as an ini under %APPDATA%\Pride. Properties are found by reflection, so a
// new MEMBER is saved, clamped and resettable with no extra wiring.
class Preferences : public QObject
{
    Q_OBJECT

        // Type
    Q_PROPERTY(QString appFont            MEMBER appFont            NOTIFY appFontChanged)
    Q_PROPERTY(QString headingFont        MEMBER headingFont        NOTIFY headingFontChanged)
    Q_PROPERTY(int     fontSizeDisplay    MEMBER fontSizeDisplay    NOTIFY fontSizeDisplayChanged)
    Q_PROPERTY(int     fontSizeHeading    MEMBER fontSizeHeading    NOTIFY fontSizeHeadingChanged)
    Q_PROPERTY(int     fontSizeBody       MEMBER fontSizeBody       NOTIFY fontSizeBodyChanged)
    Q_PROPERTY(int     fontSizeLabel      MEMBER fontSizeLabel      NOTIFY fontSizeLabelChanged)
    Q_PROPERTY(int     fontSizeCaption    MEMBER fontSizeCaption    NOTIFY fontSizeCaptionChanged)
        // Shape and spacing
    Q_PROPERTY(int     cornerRadius       MEMBER cornerRadius       NOTIFY cornerRadiusChanged)
    Q_PROPERTY(int     controlRadius      MEMBER controlRadius      NOTIFY controlRadiusChanged)
    Q_PROPERTY(int     spacingSmall       MEMBER spacingSmall       NOTIFY spacingSmallChanged)
    Q_PROPERTY(int     spacingMedium      MEMBER spacingMedium      NOTIFY spacingMediumChanged)
    Q_PROPERTY(int     spacingLarge       MEMBER spacingLarge       NOTIFY spacingLargeChanged)
        // Colour
    Q_PROPERTY(QColor  backgroundPrimary   MEMBER backgroundPrimary   NOTIFY backgroundPrimaryChanged)
    Q_PROPERTY(QColor  backgroundSecondary MEMBER backgroundSecondary NOTIFY backgroundSecondaryChanged)
    Q_PROPERTY(QColor  backgroundTertiary  MEMBER backgroundTertiary  NOTIFY backgroundTertiaryChanged)
    Q_PROPERTY(QColor  surfaceArt          MEMBER surfaceArt          NOTIFY surfaceArtChanged)
    Q_PROPERTY(QColor  accentColor         MEMBER accentColor         NOTIFY accentColorChanged)
    Q_PROPERTY(QColor  accentDeep          MEMBER accentDeep          NOTIFY accentDeepChanged)
    Q_PROPERTY(QColor  accentSubtle        MEMBER accentSubtle        NOTIFY accentSubtleChanged)
    Q_PROPERTY(QColor  goldColor           MEMBER goldColor           NOTIFY goldColorChanged)
    Q_PROPERTY(QColor  borderColor         MEMBER borderColor         NOTIFY borderColorChanged)
    Q_PROPERTY(QColor  textPrimary         MEMBER textPrimary         NOTIFY textPrimaryChanged)
    Q_PROPERTY(QColor  textSecondary       MEMBER textSecondary       NOTIFY textSecondaryChanged)
    Q_PROPERTY(QColor  textMuted           MEMBER textMuted           NOTIFY textMutedChanged)
    Q_PROPERTY(QColor  dangerColor         MEMBER dangerColor         NOTIFY dangerColorChanged)
    Q_PROPERTY(QColor  successColor        MEMBER successColor        NOTIFY successColorChanged)
        // Browsing
    Q_PROPERTY(int     tileWidth           MEMBER tileWidth           NOTIFY tileWidthChanged)
    Q_PROPERTY(bool    filterPanelCollapsed MEMBER filterPanelCollapsed NOTIFY filterPanelCollapsedChanged)
        // Settings page
    Q_PROPERTY(QVariantMap defaults READ defaults CONSTANT)
    Q_PROPERTY(QString storagePath READ storagePath CONSTANT)

public:
    explicit Preferences(QObject *parent = nullptr);
    ~Preferences() override;

    QVariantMap defaults() const { return m_defaults; }
    QString storagePath() const;
    Q_INVOKABLE QVariantMap limits(const QString &key) const;
    Q_INVOKABLE QStringList choices(const QString &key) const;
    Q_INVOKABLE void reset(const QString &key);
    Q_INVOKABLE void resetAll();
    // Settings › Colours: every colour token back to Superbia's, everything else as it is.
    Q_INVOKABLE void resetColours();

        // Type: Segoe UI for reading, the bundled heading face (spec §7) for headings and page titles.
    QString appFont =           QStringLiteral("Segoe UI");
    QString headingFont =       QStringLiteral("Cinzel");
    int     fontSizeDisplay =   26;   // a page's own title, an exercise's name
    int     fontSizeHeading =   18;   // section headings
    int     fontSizeBody =      14;   // body text, list rows, buttons
    int     fontSizeLabel =     13;   // tile titles, field labels, chips
    int     fontSizeCaption =   12;   // metadata, counts
        // Shape and spacing
    int     cornerRadius =      12;   // cards, tiles
    int     controlRadius =     8;    // buttons and fields; chips are fully round
    int     spacingSmall =      8;
    int     spacingMedium =     16;
    int     spacingLarge =      24;
        // Colour ("Superbia", spec §7): violet into royal purple, gold for crowns and suggestions, on a near-black
        // ink ground. Pictures always sit on surfaceArt.
    QColor  backgroundPrimary =   QColor(0x0e0b14); // ink: the page behind everything
    QColor  backgroundSecondary = QColor(0x1a1424); // surface: panels, the rail, cards and tiles
    QColor  backgroundTertiary =  QColor(0x251c33); // fields, hovered rows and tiles
    QColor  surfaceArt =          QColor(0x120e19); // under every picture
    QColor  accentColor =         QColor(0x8e5cf5); // royal: focus, selection; the gradient's end
    QColor  accentDeep =          QColor(0x6b3fd9); // violet: the gradient's start
    QColor  accentSubtle =        QColor(0x2b1f45); // a chosen chip, the active rail button
    QColor  goldColor =           QColor(0xe3b341); // crowns and suggestions only
    QColor  borderColor =         QColor(0x2f2542); // hairlines, field borders
    QColor  textPrimary =         QColor(0xede7f6);
    QColor  textSecondary =       QColor(0xc4b8da);
    QColor  textMuted =           QColor(0x8a7fa0); // placeholders, metadata, counts
    QColor  dangerColor =         QColor(0xe5484d); // errors; destructive buttons are outlined in it
    QColor  successColor =        QColor(0x4fbf8b);
        // Browsing
    int     tileWidth =         200;
    bool    filterPanelCollapsed = false;

signals:
    void appFontChanged();
    void headingFontChanged();
    void fontSizeDisplayChanged();
    void fontSizeHeadingChanged();
    void fontSizeBodyChanged();
    void fontSizeLabelChanged();
    void fontSizeCaptionChanged();
    void cornerRadiusChanged();
    void controlRadiusChanged();
    void spacingSmallChanged();
    void spacingMediumChanged();
    void spacingLargeChanged();
    void backgroundPrimaryChanged();
    void backgroundSecondaryChanged();
    void backgroundTertiaryChanged();
    void surfaceArtChanged();
    void accentColorChanged();
    void accentDeepChanged();
    void accentSubtleChanged();
    void goldColorChanged();
    void borderColorChanged();
    void textPrimaryChanged();
    void textSecondaryChanged();
    void textMutedChanged();
    void dangerColorChanged();
    void successColorChanged();
    void tileWidthChanged();
    void filterPanelCollapsedChanged();

private slots:
    void scheduleSave();

private:
    void load();
    void save();
    QVariant clamped(const QString &key, const QVariant &value) const;

    QVariantMap m_defaults;
    QTimer m_saveTimer;
};
