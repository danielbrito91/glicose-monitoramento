from sqlalchemy.sql.sqltypes import Boolean, DateTime
from werkzeug.datastructures import Authorization
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, insert, create_engine, Table, Column, Integer, String, MetaData
from helpers import apology, login_required
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import pandas as pd
import os
import matplotlib.pyplot as plt
import io

# Configure application
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///glicose.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#https://stackoverflow.com/questions/33738467/how-do-i-know-if-i-can-disable-sqlalchemy-track-modifications

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = 'filesystem'
app.secret_key = 'super secret key'


REFEICOES = [
    'Café da manhã',
    'Lanche da manhã',
    'Almoço',
    'Lanche da tarde',
    'Janta',
    'Ceia']

# Configure database
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String, unique=True)
    name = db.Column(db.String)
    email = db.Column(db.String, unique=True)
    hash = db.Column(db.String)

    def __init__(self, username, name, email, hash):
        self.username = username
        self.name = name
        self.email = email
        self.hash = hash

class Refeicao(db.Model):
    __tablename__ = 'refeicao'

    id = db.Column(db.Integer, primary_key=True,autoincrement=True)
    data_ref = db.Column(db.DateTime)
    tipo = db.Column(db.String)
    descricao = db.Column(db.String)
    usuario = db.Column(db.Integer, ForeignKey('users.id'))

    def __init__(self, data_ref, tipo, descricao, usuario):
        self.data_ref = data_ref
        self.tipo = tipo
        self.descricao = descricao
        self.usuario = usuario

class Glicose(db.Model):
    __tablename__ = 'glicose'

    id = db.Column(db.Integer, primary_key=True)
    resultado = db.Column(db.Float)
    data = db.Column(db.DateTime)
    jejum = db.Column(db.Boolean)
    observacao = db.Column(db.String)
    usuario = db.Column(db.Integer, ForeignKey('users.id'))

    def __init__(self, resultado, data, jejum, observacao, usuario):
        self.resultado = resultado
        self.data = data
        self.jejum = jejum
        self.observacao = observacao
        self.usuario = usuario

@app.route('/')
@login_required
def index():

    user_query = User.query.filter(User.id == session['user_id']).first()
    
    user_glic = Glicose.query.filter(Glicose.usuario == session['user_id']).order_by(Glicose.data)
    
    user_meals = Refeicao.query.filter(Refeicao.usuario == session['user_id']).order_by(Refeicao.data_ref)

    if user_glic.count() > 0 and user_meals.count() > 0:

        glic_dates = []
        glic_glics = []

        meals_dates = []
        meals_tipo = []
        meals_desc = []

        for g in user_glic:
            glic_dates.append(g.data)
            glic_glics.append(g.resultado)
        
        for m in user_meals:
            meals_dates.append(m.data_ref)
            meals_tipo.append(m.tipo)
            meals_desc.append(m.descricao)
        
        glic_df = pd.DataFrame(list(zip(glic_dates, glic_glics)), columns=['data_glic', 'resultado'])
        meals_df = pd.DataFrame(list(zip(meals_dates, meals_tipo)), columns=['data_ref', 'tipo'])

        # procura pela ultima refeicao
        ultima_ref_data = []
        ultima_ref_tipo = []

        for i in range(glic_df.shape[0]):
            ultima = max(meals_df[meals_df["data_ref"] < glic_df.iloc[i]["data_glic"]]["data_ref"])
            ultima_ref_data.append(ultima)
            ultima_ref_tipo.append(meals_df[meals_df["data_ref"] ==  ultima]["tipo"].values[0])

        # cruzar glicemias com ultimas refeicos
        glicemia_refeicao = pd.concat([glic_df, pd.Series(ultima_ref_data),
                                    pd.Series(ultima_ref_tipo)],
                                    axis = 1, ignore_index=True)

        glicemia_refeicao.columns = ['data_glic', 'resultado',
                                    'ultima_ref_data', 'ultima_ref_tipo']

        glicemia_refeicao['tempo'] = (glicemia_refeicao['data_glic'] -
                                    glicemia_refeicao['ultima_ref_data'])
        
        glicemia_refeicao['tempo'] = round(glicemia_refeicao["tempo"].dt.total_seconds() / (60 * 60), 2)

        df = glicemia_refeicao[['data_glic', 'resultado', 'tempo']]
        df.columns = ['Data', 'Glicemia (mg/dL)', 'Tempo da última refeição (h)']
        df.name = ''
    
        return render_template('index.html', name = user_query.name, tables = [df.to_html(classes = 'data', index=False)], titles = df.columns.values)
    else:

        df = pd.DataFrame(columns=['Data', 'Glicemia (mg/dL)', 'Tempo da última refeição (h)'])

        return render_template('index.html', name = user_query.name, tables = [df.to_html(classes = 'data', index=False)], titles = df.columns.values)
        # do something

  
def checkbox_bol(check):
    if check == 'on':
        return True
    else:
        return False

@app.route('/history')
@login_required
def historico():

    # query glicose do usuario
    user_glic = Glicose.query.filter(Glicose.usuario == session['user_id']).order_by(Glicose.data)
    
    return render_template('history.html', user_glic = user_glic, plot = plt.show())

@app.route('/insert_b_glucose', methods=['GET', 'POST'])
@login_required
def insert_b_glucose():
    if request.method == 'POST':

        if len(request.form.get('data_hora')) == 0 or len(request.form.get('resultado')) == 0:
            return apology('Informar data e resultado', 403)

        glic = Glicose(
            request.form['resultado'],
            datetime.strptime(
                request.form['data_hora'].replace('T', ' '),
                '%Y-%m-%d %H:%M'),
            checkbox_bol(request.form.get('jejum')),
            request.form['observacao'],
            session['user_id']
            )
        
        db.session.add(glic)
        db.session.commit()

        return redirect('/')
    else:
        return render_template('insert_b_glucose.html')

@app.route('/login', methods=['GET', 'POST'])
def login():

    session.clear()

    if request.method == 'POST':
        # query db for username
        user = (User.query
                .filter_by(username = request.form.get('username'))
                ).first()
        
        if user is None:
            return apology('Informar usuário', 403)
        
        if user is None or not check_password_hash(user.hash, request.form.get('password')):
            return apology('Usuário ou senha inválido(s)', 403)

        session['user_id'] = user.id

        print(user)

        return redirect("/")
    else:
        return render_template('login.html')

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

@app.route('/insert_meal', methods=['GET', 'POST'])
@login_required
def refeicao():
    if request.method == 'POST':
        
         # check data
        if len(request.form.get('data_hora')) == 0:
            return apology('Informar data de refeicao', 403)

        ref = Refeicao(
            datetime.strptime(
                request.form['data_hora'].replace('T', ' '),
                '%Y-%m-%d %H:%M'),
            request.form['refeicao'],
            request.form['descricao'],
            session['user_id']
            )
        
        db.session.add(ref)
        db.session.commit()


        return redirect('/')
    else:
        return render_template('insert_meal.html', refeicoes=REFEICOES)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        # check usuario ou email existente
        if User.query.filter_by(username = request.form['username']).first():
            return apology('Usário já cadastrado', 403)
        
        if User.query.filter_by(email = request.form['email']).first():
            return apology('Email já cadastrado', 403)

        # check tamanho senha
        if len(request.form.get('password')) < 3:
            return apology('Informar senha com mais de 2 caracteres')

        # check conflito senha
        if request.form.get('password') != request.form.get('confirmation'):
            return apology('As senhas registradas diferem uma da outra', 403)

        # Register the user into the database
        user = User(
            request.form['username'],
            request.form['name'],
            request.form['email'],
            generate_password_hash(request.form['password'])
            )
        
        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id
         
        return redirect('/')
    else:
        return render_template('register.html')

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)