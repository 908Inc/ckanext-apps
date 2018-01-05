from wtforms import TextAreaField, StringField, validators, IntegerField
from wtforms import Form


class CreateAppForm(Form):
    name = StringField(validators=[validators.InputRequired(), validators.Length(min=1)])
    content = TextAreaField(validators=[validators.InputRequired(), validators.Length(min=1)])
    logo = StringField(validators=[validators.InputRequired(),
                                   validators.Length(min=1)])
    board_id = IntegerField(validators=[validators.InputRequired()])


class CreateBoardForm(Form):
    name = StringField(validators=[validators.InputRequired(), validators.Length(min=1)])
    slug = StringField(validators=[validators.InputRequired(),
                                   validators.Length(min=1),
                                   validators.Regexp('^[a-z0-9\-]*$')])
