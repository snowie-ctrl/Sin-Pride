import QtQuick
import QtTest
import "../../qml/logic/forms.mjs" as Forms
import "../../qml/logic/words.mjs" as Words

TestCase {
    name: "Forms"

    function test_signInLengthsMatchTheServer_data() {
        return [
            { tag: "fine", u: "ann", p: "12345678", want: "" },
            { tag: "short username", u: "an", p: "12345678", want: Words.usernameLength },
            { tag: "long username", u: "a".repeat(33), p: "12345678", want: Words.usernameLength },
            { tag: "username at 32", u: "a".repeat(32), p: "12345678", want: "" },
            { tag: "spaces trimmed", u: "  an  ", p: "12345678", want: Words.usernameLength },
            { tag: "short password", u: "ann", p: "1234567", want: Words.passwordLength },
            { tag: "password at 256", u: "ann", p: "p".repeat(256), want: "" },
            { tag: "long password", u: "ann", p: "p".repeat(257), want: Words.passwordLength },
            { tag: "nothing typed", u: "", p: "", want: Words.enterUsernameAndPassword },
        ]
    }

    function test_signInLengthsMatchTheServer(data) {
        compare(Forms.signInProblem(data.u, data.p), data.want)
    }
}
