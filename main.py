from authlib.integrations.flask_client import OAuth
from flask import abort, Flask, render_template, request, url_for, jsonify
import auth_constants
import boat
import constants
import helpers
import load
import requests
import user

app = Flask(__name__)
app.secret_key = auth_constants.APP_SECRET_KEY
app.register_blueprint(boat.bp)
app.register_blueprint(user.bp)
app.register_blueprint(load.bp)

oauth = OAuth(app)

oauth.register("auth0", client_id=auth_constants.AUTH0_CLIENT_ID,
               client_secret=auth_constants.AUTH0_CLIENT_SECRET,
               client_kwargs={"scope": "openid profile email"},
               server_metadata_url=f'https://{auth_constants.AUTH0_DOMAIN}/.well-known/openid-configuration')


# render home page
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login", methods=['GET', 'POST'])
def login():
    # redirect to auth0 to login
    if request.method == 'GET':
        return oauth.auth0.authorize_redirect(redirect_uri=url_for("callback", _external=True))
    # log in using provided username and password
    elif request.method == 'POST':
        content = request.get_json()
        body = {'grant_type': 'password',
                'username': content["username"],
                'password': content["password"],
                'client_id': auth_constants.AUTH0_CLIENT_ID,
                'client_secret': auth_constants.AUTH0_CLIENT_SECRET
                }
        headers = {'content-type': 'application/json'}
        url = 'https://' + auth_constants.AUTH0_DOMAIN + '/oauth/token'
        r = requests.post(url, json=body, headers=headers)
        return r.text, 200, {'Content-Type': 'application/json'}
    else:
        abort(405, description="Method Not Allowed")


# get jwt and render user info page
@app.route('/callback', methods=['GET', 'POST'])
def callback():
    token = oauth.auth0.authorize_access_token()
    usr = find_user(token)
    if not usr:
        usr = create_user(token)
    return render_template('user_info.html', user_id=usr.id, jwt=token['id_token'])


def find_user(token):
    users = helpers.fetch_list(constants.users)
    for usr in users:
        if usr['sub'] == token['userinfo']['sub']:
            return usr
    return None


def create_user(token):
    user_data = {'name': token['userinfo']['name'], 'sub': token['userinfo']['sub']}
    usr = helpers.create_new_item(user_data, constants.users)
    return usr


@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(406)
@app.errorhandler(415)
def handle_error(e):
    return jsonify(str(e)), e.code


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
