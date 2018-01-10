from wtforms import (TextAreaField, StringField, validators,
                     IntegerField, FileField, Form)


class CreateAppForm(Form):
    name = StringField(validators=[validators.InputRequired(),
                                   validators.Length(min=1)])
    content = TextAreaField(validators=[validators.InputRequired(),
                                        validators.Length(min=1)])
    image_url = FileField()
    board_id = IntegerField(validators=[validators.InputRequired()])
    external_link = StringField(validators=[validators.InputRequired(),
                                            validators.Length(min=1)])


class CreateBoardForm(Form):
    name = StringField(validators=[validators.InputRequired(),
                                   validators.Length(min=1)])
    slug = StringField(validators=[validators.InputRequired(),
                                   validators.Length(min=1),
                                   validators.Regexp('^[a-z0-9\-]*$')])


class CloseAppForm(Form):
    closed_message = StringField()
