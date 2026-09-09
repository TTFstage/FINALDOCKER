from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, Regexp, ValidationError


def normalize_code(code: str) -> str:
    """Normalizza un codice gruppo rimuovendo spazi e trattini."""
    return code.replace('-', '').replace(' ', '').lower()


class CreateGroupForm(FlaskForm):
    """Form per la creazione di un nuovo gruppo."""
    name = StringField(
        'Nome del Gruppo',
        validators=[
            DataRequired(message='Il nome del gruppo è obbligatorio.'),
            Length(
                min=2,
                max=100,
                message='Il nome deve essere tra %(min)d e %(max)d caratteri.'
            )
        ],
        render_kw={'placeholder': 'Es. Team Progetto Alpha', 'autofocus': True}
    )
    description = TextAreaField(
        'Descrizione',
        validators=[
            Optional(),
            Length(
                max=500,
                message='La descrizione non può superare %(max)d caratteri.'
            )
        ],
        render_kw={
            'placeholder': 'Breve descrizione sugli obiettivi o partecipanti del gruppo...',
            'rows': 3
        }
    )


class JoinGroupForm(FlaskForm):
    """Form per unirsi a un gruppo tramite codice."""
    code = StringField(
        'Codice Gruppo',
        validators=[
            DataRequired(message='Il codice del gruppo è obbligatorio.'),
            Length(
                min=9,
                max=15,
                message='Il codice deve essere composto da almeno %(min)d caratteri (trattini inclusi).'
            )
        ],
        render_kw={
            'placeholder': 'es. abc-defg-hij',
            'autocomplete': 'off',
            'autofocus': True
        }
    )


class JoinByTokenForm(FlaskForm):
    """Form per accettare un invito tramite link token. Non ha campi visibili."""
    pass


class ChangeRoleForm(FlaskForm):
    """Form per cambiare il ruolo di un membro."""
    role = SelectField(
        'Nuovo Ruolo',
        validators=[DataRequired(message='Seleziona un ruolo valido.')],
        choices=[
            ('admin', 'Admin'),
            ('member', 'Membro')
        ],
        render_kw={'class': 'form-control', 'style': 'width: auto;'}
    )
