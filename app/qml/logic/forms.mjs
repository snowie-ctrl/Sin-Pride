// Field checks that match the server's (spec §4), so a person hears what's wrong before anything is sent. Each
// returns "" when the value is fine, otherwise the words to show (words.mjs). server/prideRoutes.py and
// server/prideChecks.py hold the same limits.
import * as Words from "words.mjs"

export const USERNAME = { min: 3, max: 32 }
export const PASSWORD = { min: 8, max: 256 }

export function signInProblem(username, password) {
    const name = String(username || "").trim()
    const secret = String(password || "")
    if (!name.length || !secret.length)
        return Words.enterUsernameAndPassword
    if (name.length < USERNAME.min || name.length > USERNAME.max)
        return Words.usernameLength
    if (secret.length < PASSWORD.min || secret.length > PASSWORD.max)
        return Words.passwordLength
    return ""
}
