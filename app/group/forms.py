from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


def normalize_code(code: str) -> str:
    """Normalizes a group code by removing spaces and dashes."""
    return code.replace('-', '').replace(' ', '').lower()


class CreateGroupForm(FlaskForm):
    """Form for creating a new group."""
    name = StringField(
        'Group Name',
        validators=[
            DataRequired(message='Group name is required.'),
            Length(
                min=2,
                max=100,
                message='Name must be between %(min)d and %(max)d characters.'
            )
        ],
        render_kw={'placeholder': 'e.g. Project Alpha Team', 'autofocus': True}
    )
    description = TextAreaField(
        'Description',
        validators=[
            Optional(),
            Length(
                max=500,
                message='Description cannot exceed %(max)d characters.'
            )
        ],
        render_kw={
            'placeholder': 'Brief description of the group goals or members...',
            'rows': 3
        }
    )


class JoinGroupForm(FlaskForm):
    """Form for joining a group via code."""
    code = StringField(
        'Group Code',
        validators=[
            DataRequired(message='Group code is required.'),
            Length(
                min=9,
                max=15,
                message='Code must be at least %(min)d characters (dashes included).'
            )
        ],
        render_kw={
            'placeholder': 'e.g. abc-defg-hij',
            'autocomplete': 'off',
            'autofocus': True
        }
    )


class JoinByTokenForm(FlaskForm):
    """Form for accepting an invite via token link. Has no visible fields."""


class ChangeRoleForm(FlaskForm):
    """Form for changing a member's role."""
    role = SelectField(
        'New Role',
        validators=[DataRequired(message='Please select a valid role.')],
        choices=[
            ('admin', 'Admin'),
            ('member', 'Member')
        ],
        render_kw={'class': 'form-control', 'style': 'width: auto;'}
    )
