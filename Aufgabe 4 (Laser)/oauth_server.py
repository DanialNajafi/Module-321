from flask import Flask, request

app = Flask(__name__)

# 1. Authorize Endpunkt (Wird im Browser aufgerufen)
@app.route('/authorize', methods=['GET'])
def authorize():
    redirect_uri = request.args.get('redirect_uri')
    state = request.args.get('state')
    
    # Callback-URL generieren, die den Autorisierungs-Code an den Laser zurückgibt
    callback_url = f"{redirect_uri}?code=geheimer_auth_code_123&state={state}"
    
    return f'''
        <div style="text-align: center; font-family: sans-serif; margin-top: 50px;">
            <h2>Laser-Sicherheitssystem (OAuth2)</h2>
            <p>Techniker-Authentifizierung erforderlich.</p>
            <a href="{callback_url}">
                <button style="padding: 12px 24px; font-size: 16px; background-color: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer;">
                    Freischalten & Anmelden
                </button>
            </a>
        </div>
    '''

# 2. Token Endpunkt (Der Laser fordert hier im Hintergrund das Token an)
@app.route('/token', methods=['POST'])
def token():
    # Der Laser tauscht seinen Auth-Code gegen ein Access Token ein
    return {
        "access_token": "laser_gültiges_access_token_999",
        "token_type": "Bearer",
        "expires_in": 3600
    }

if __name__ == '__main__':
    # Startet auf Port 2019
    app.run(host='0.0.0.0', port=2019)