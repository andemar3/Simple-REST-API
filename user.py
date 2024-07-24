from flask import abort, Blueprint, jsonify, request
from google.cloud import datastore
import constants
import helpers

client = datastore.Client()

bp = Blueprint('user', __name__, url_prefix='/users')


@bp.route('/', methods=['GET'])
def user_get_post():
    # get list of all users
    if request.method == 'GET':
        helpers.check_accepts_json_res(request)
        users = helpers.fetch_list(constants.users)
        for usr in users:
            usr = _add_ids(usr)
            usr = _remove_sub(usr)
        return helpers.create_response(jsonify(users), 200, constants.json)
    else:
        abort(405, description="Method Not Allowed")


def _add_ids(usr):
    usr.update({'id': usr.id})
    return usr


def _remove_sub(usr):
    del usr['sub']
    return usr
