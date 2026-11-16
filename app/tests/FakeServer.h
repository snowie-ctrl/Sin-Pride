// Copied from Gluttony app/tests/FakeServer.h at c1ed705; answers and records by method too.
#pragma once
#include <QHash>
#include <QPointer>
#include <QTcpServer>
#include <QTcpSocket>
#include <QUrl>

#include <functional>
#include <memory>


// A tiny HTTP server for the Controller tests. Each path answers with canned
// JSON, and every request is remembered, so a test can check both what the
// Controller asked for and what it made of the answer without the real API.
class FakeServer : public QTcpServer
{
public:
    QHash<QString, QByteArray> responses;   // path without query -> JSON body
    QList<QUrl> requests;                   // every request, in arrival order
    QList<QByteArray> bodies;               // each request's body, in step with `requests`
    QList<QByteArray> heads;                // each request's raw head, in step with `requests`
    QList<QByteArray> methods;              // each request's HTTP method, in step with `requests`
    QHash<QString, QByteArray> methodResponses;   // "POST /api/pride/programs" -> body, before responses
    QHash<QString, int> methodStatuses;           // likewise, a status; queued answers still win
    QHash<QString, QList<QByteArray>> queued;   // path -> bodies served first, in order, then `responses`
    QHash<QString, int> statuses;               // path -> HTTP status, 200 when absent
    QHash<QString, QList<int>> queuedStatuses;  // path -> statuses served first, in order, then `statuses`

    // path -> how many of its next replies to park instead of sending, so a
    // test can answer a later request first. releaseHeld() sends the parked ones.
    QHash<QString, int> holdNext;

    // Sends every parked reply, in the order its request arrived.
    void releaseHeld()
    {
        const auto parked = std::move(m_parked);
        m_parked.clear();
        for (const auto &send : parked)
            send();
    }

    FakeServer() { listen(QHostAddress::LocalHost, 0); }

protected:
    void incomingConnection(qintptr handle) override
    {
        auto *socket = new QTcpSocket(this);
        socket->setSocketDescriptor(handle);
        auto buffer = std::make_shared<QByteArray>();

        connect(socket, &QTcpSocket::readyRead, this, [this, socket, buffer]() {
            buffer->append(socket->readAll());
            const int headerEnd = buffer->indexOf("\r\n\r\n");
            if (headerEnd < 0)
                return;

            const QByteArray head = buffer->left(headerEnd);
            int length = 0;
            for (const QByteArray &line : head.split('\n')) {
                const QByteArray trimmed = line.trimmed();
                if (trimmed.toLower().startsWith("content-length:"))
                    length = trimmed.mid(15).trimmed().toInt();
            }
            if (buffer->size() < headerEnd + 4 + length)
                return;

            const QByteArray method = head.left(head.indexOf(' '));
            const QUrl url(QString::fromLatin1(head.split(' ').value(1)));
            requests.append(url);
            methods.append(method);
            heads.append(head);
            bodies.append(buffer->mid(headerEnd + 4, length));

            // Method answers sit between the path's answers and the queue: a queued answer wins, then
            // "METHOD path", then the path alone.
            const QString key = QString::fromLatin1(method) + QLatin1Char(' ') + url.path();
            QByteArray body = responses.value(url.path(), R"({"status":"ok","data":[]})");
            if (methodResponses.contains(key))
                body = methodResponses.value(key);
            QList<QByteArray> &line = queued[url.path()];
            if (!line.isEmpty())
                body = line.takeFirst();
            int status = statuses.value(url.path(), 200);
            if (methodStatuses.contains(key))
                status = methodStatuses.value(key);
            QList<int> &statusLine = queuedStatuses[url.path()];
            if (!statusLine.isEmpty())
                status = statusLine.takeFirst();
            const QByteArray reason = status == 200 ? "OK" : status == 401 ? "Unauthorized"
                                    : status == 400 ? "Bad Request" : status == 403 ? "Forbidden" : status == 404 ? "Not Found"
                                    : status == 409 ? "Conflict" : "Error";
            const QPointer<QTcpSocket> target(socket);
            const auto send = [target, status, reason, body]() {
                if (!target)
                    return;
                target->write("HTTP/1.1 " + QByteArray::number(status) + " " + reason + "\r\n"
                              "Content-Type: application/json\r\nConnection: close\r\n"
                              "Content-Length: " + QByteArray::number(body.size()) + "\r\n\r\n" + body);
                target->disconnectFromHost();
            };
            int &held = holdNext[url.path()];
            if (held > 0) {
                --held;
                m_parked.append(send);
            } else {
                send();
            }
        });
    }

private:
    QList<std::function<void()>> m_parked;
};
