from flask import Flask
from flask_security import RegisterFormV2
from wtforms import SelectField, StringField
from wtforms.validators import DataRequired, Length, Optional, Regexp
from flask_wtf import FlaskForm


class ExtendedRegisterForm(RegisterFormV2):
    """Form esteso di registrazione con campi aggiuntivi."""
    phone_number = StringField(
        'Numero di Telefono',
        validators=[
            Optional(),
            Length(
                max=20,
                message='Il numero di telefono non può superare %(max)d caratteri.'
            ),
            Regexp(
                r'^[\d\s\+\-\(\)]*$',
                message='Il numero di telefono contiene caratteri non validi.'
            )
        ],
        render_kw={'placeholder': '+39 333 1234567'}
    )

    # Override del validatore username per messaggi più chiari
    @classmethod
    def get_username_validators(cls):
        return [
            Length(
                min=3,
                max=50,
                message='Lo username deve essere tra %(min)d e %(max)d caratteri.'
            )
        ]

    # Override del validatore email per messaggi più chiari
    @classmethod
    def get_email_validators(cls):
        return [
            Length(
                min=5,
                max=120,
                message='L\'email deve essere tra %(min)d e %(max)d caratteri.'
            )
        ]

    # Override del validatore password per messaggi più chiari
    @classmethod
    def get_password_validators(cls, field):
        return []


class SOSContactForm(FlaskForm):
    """Form per aggiungere/modificare un contatto SOS."""
    name = StringField(
        'Nome Completo',
        validators=[
            DataRequired(message='Il nome è obbligatorio.'),
            Length(min=2, max=100, message='Il nome deve essere tra %(min)d e %(max)d caratteri.')
        ],
        render_kw={'placeholder': 'Es. Maria Rossi', 'autofocus': True}
    )
    phone = StringField(
        'Numero di Telefono',
        validators=[
            DataRequired(message='Il numero di telefono è obbligatorio.'),
            Length(min=5, max=20, message='Il numero deve essere tra %(min)d e %(max)d caratteri.'),
            Regexp(
                r'^[\d\s\+\-\(\)]+$',
                message='Numero di telefono non valido. Usa solo cifre, spazi e i caratteri + - ( ).'
            )
        ],
        render_kw={'placeholder': 'Es. +39 333 1234567'}
    )
    relationship = SelectField(
        'Relazione',
        validators=[Optional()],
        choices=[
            ('', 'Seleziona...'),
            ('Coniuge/Partner', 'Coniuge/Partner'),
            ('Genitore', 'Genitore'),
            ('Fratello/Sorella', 'Fratello/Sorella'),
            ('Figlio/a', 'Figlio/a'),
            ('Amico/a', 'Amico/a'),
            ('Collega', 'Collega'),
            ('Altro', 'Altro')
        ],
        default=''
    )
    priority = SelectField(
        'Priorità',
        validators=[Optional()],
        choices=[
            ('0', 'Bassa'),
            ('1', 'Media'),
            ('2', 'Alta')
        ],
        default='1',
        coerce=int
    )
