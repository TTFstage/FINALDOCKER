from flask_security import RegisterFormV2
from wtforms import StringField
from wtforms.validators import Length, Optional


class ExtendedRegisterForm(RegisterFormV2):
    phone_number = StringField('Phone Number', validators=[Optional(), Length(max=20)])
