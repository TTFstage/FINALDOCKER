from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)

# Configurazione del server SMTP
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'la_tua_email@gmail.com'
app.config['MAIL_PASSWORD'] = 'password'  # Usa una Password per le App
app.config['MAIL_DEFAULT_SENDER'] = 'la_tua_email@gmail.com'

mail = Mail(app)

@app.route("/")
def invia_mail():
    msg = Message(
        subject="Test Email da Flask",
        recipients=['email@esempio.com'],
        body='Prova di invio email con Flask-Mail.'
    )
    
    # Per inviare email in formato HTML:
    # msg.html = "Benvenuto!Email di prova"
    
    try:
        mail.send(msg)
        return "Email inviata con successo!"
    except Exception as e:  # noqa: BLE001
        return f"Errore nell'invio: {e!s}"

if __name__ == "__main__":
    app.run(debug=True)