// Copied from Gluttony app/LinkSuppressor.h at c1ed705; PRIDE_ names.
#pragma once

#include <QDebug>
#include <QObject>
#include <QUrl>

// For the dev hooks (PRIDE_GRAB, PRIDE_CLICK): a link a page opens
// is not handed to the owner's browser while a grab is running. Only the
// scheme is logged, never the address.
class LinkSuppressor : public QObject
{
    Q_OBJECT

public slots:
    void suppress(const QUrl &url)
    {
        qInfo().noquote() << "opening" << url.scheme() << "link suppressed during a grab";
    }
};
