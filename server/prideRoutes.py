"""
Pride's app routes at /api/pride: the reachability check, accounts (sign-in, sign-up with a login key, a device that
signs itself in, sign-out, devices) and the exercise catalog with its pictures. docs/api.md is the contract for the
desktop app and the iOS app. Every route needs a session (prideSession.py) unless PUBLIC_ROUTES names it, so a route
added later cannot forget the check. What a person owns (profile, programs, workouts) arrives in prideUserRoutes.py in
milestone 2.
"""
import hashlib
import re
import secrets
from datetime import timedelta

from flask import Blueprint, jsonify, request, send_file
from werkzeug.security import check_password_hash, generate_password_hash

from . import prideCatalog as catalog, prideSession as session

prideBP = Blueprint("pride", __name__)
session.install(prideBP)
database = session.database
fail = session.fail


def ok(data=None, status="ok", **extra):
    answer = {"status": status}
    if data is not None:
        answer["data"] = data
    answer.update(extra)
    return jsonify(answer), 200


def body():
    """The JSON body, or {} when there is none or it isn't an object, so validation can say what is missing."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@prideBP.route("/ping", methods=["GET"])
def ping():
    return ok()
