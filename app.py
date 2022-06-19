from flask import Flask, render_template, flash, request, redirect, url_for
from datetime import datetime 
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash 
from datetime import date
from webforms import LoginForm, PostForm, UserForm, PasswordForm, NamerForm, SearchForm
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from webforms import LoginForm, PostForm, UserForm, PasswordForm, NamerForm
from flask_ckeditor import CKEditor
from werkzeug.utils import secure_filename
import uuid as uuid
import os
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import lxml.html as lh
from datetime import datetime

# Create a Flask Instance
app = Flask(__name__)
# Add CKEditor
ckeditor = CKEditor(app)
# Add Database
# Old SQLite DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://fvmdxyjigwbmiu:d31d36c7613e08f7ad37a6e40007189d7f2f44fbc99234b339994780a122d870@ec2-3-214-190-189.compute-1.amazonaws.com:5432/d17b5scj97ckqe'

# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://kzzgtepmihknds:032e659278e70aeeba6bc9ae8d4a22e6257ca5ce85feb9a5bf8c18f2a683087e@ec2-44-196-174-238.compute-1.amazonaws.com:5432/da3ak0ru9lfrn1'

picks_path = "usopen-player-selections_v2.csv"
# New MySQL DB
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://username:password@localhost/db_name'
#app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password123@localhost/our_users'
# Secret Key!
app.config['SECRET_KEY'] = "my super secret key that no one is supposed to know"
# Initialize The Database

UPLOAD_FOLDER = 'static/images/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
migrate = Migrate(app, db)

COURSE_PAR = 70
TOTAL_GOLFERS_SCORED = 6

def round_tracker():
	today = datetime.today().isoweekday()
	if today == 4:
		return COURSE_PAR
	elif today == 5:
		return COURSE_PAR * 2
	elif today == 6:
		return COURSE_PAR * 3
	else:
		return COURSE_PAR * 4

def cut_detection(row):
    if row['SCORE'] == 'CUT':
        return 
    else:
        return row['TOT']

def cleanup(row):
    if row['POS'][:1] == 'T':
        return row['POS'][1:]
    else:
        return row['POS'][:]

# Flask_Login Stuff
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
	return Users.query.get(int(user_id))

# Pass Stuff To Navbar
@app.context_processor
def base():
	form = SearchForm()
	return dict(form=form)

# Create Admin Page
@app.route('/admin')
@login_required
def admin():
	id = current_user.id
	if id == 1:
		return render_template("admin.html")
	else:
		flash("Sorry you must be the Admin to access the Admin Page...")
		return redirect(url_for('dashboard'))



# Create Search Function
@app.route('/search', methods=["POST"])
def search():
	form = SearchForm()
	posts = Posts.query
	if form.validate_on_submit():
		# Get data from submitted form
		post.searched = form.searched.data
		# Query the Database
		posts = posts.filter(Posts.content.like('%' + post.searched + '%'))
		posts = posts.order_by(Posts.title).all()

		return render_template("search.html",
		 form=form,
		 searched = post.searched,
		 posts = posts)


@app.route('/pool_standings')
def pool_standings():
	url="http://www.espn.com/golf/leaderboard"
	page = requests.get(url)
	doc = lh.fromstring(page.content)
	tr_elements = doc.xpath('//tr')
	#Create empty list
	col=[]
	i=0
	#For each row, store each first element (header) and an empty list
	for t in tr_elements[0]:
		i+=1
		name=t.text_content()
		col.append((name,[]))
	
	#Since out first row is the header, data is stored on the second row onwards
	for j in range(1,len(tr_elements)):
		#T is our j'th row
		T=tr_elements[j]
		#i is the index of our column
		i=0
		#Iterate through each element of the row
		for t in T.iterchildren():
			data=t.text_content() 
			#Check if row is empty
			if i>0:
			#Convert any numerical value to integers
				try:
					data=int(data)
				except:
					pass
			#Append the data to the empty list of the i'th column
			col[i][1].append(data)
			#Increment i for the next column
			i+=1
	
	Dict={title:column for (title,column) in col}
	df=pd.DataFrame(Dict)
	max_score = df['TOT'].max()
	df_picks = pd.read_csv(picks_path)
	df_final = df_picks.merge(df,on='PLAYER',how='left')
	df_final['TOT'].replace('--',999,inplace=True)
	df_final.dropna(inplace=True)
	df_final['TOT'] = df_final.apply(lambda x: max_score if x['SCORE'] == 'CUT' else x['TOT'], axis=1)
	df_final.sort_values(by=['Team Name','TOT'],ascending=True,inplace=True)
	df_final = df_final.groupby('Team Name').head(TOTAL_GOLFERS_SCORED)
	
	df_final_two = df_final.groupby('Team Name')['TOT'].sum().reset_index().sort_values(by='TOT',ascending=True)
	df_final_two['Position'] = df_final_two['TOT'].rank(method='min')
	df_final_two.sort_values(by='Position',inplace=True)
	df_final_two['Final Score'] = df_final_two['TOT'] - (TOTAL_GOLFERS_SCORED * round_tracker())
	todays_date_tidy = f'Updated as of {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}'
	return render_template("pool-standings.html",df_final=df_final_two, updated_date = todays_date_tidy)



@app.route('/pool_raw_data')
def pool_raw_data():
	url="http://www.espn.com/golf/leaderboard"
	page = requests.get(url)
	doc = lh.fromstring(page.content)
	tr_elements = doc.xpath('//tr')
	#Create empty list
	col=[]
	i=0
	#For each row, store each first element (header) and an empty list
	for t in tr_elements[0]:
		i+=1
		name=t.text_content()
		col.append((name,[]))
	
	#Since out first row is the header, data is stored on the second row onwards
	for j in range(1,len(tr_elements)):
		#T is our j'th row
		T=tr_elements[j]
		#i is the index of our column
		i=0
		#Iterate through each element of the row
		for t in T.iterchildren():
			data=t.text_content() 
			#Check if row is empty
			if i>0:
			#Convert any numerical value to integers
				try:
					data=int(data)
				except:
					pass
			#Append the data to the empty list of the i'th column
			col[i][1].append(data)
			#Increment i for the next column
			i+=1
	
	Dict={title:column for (title,column) in col}
	df=pd.DataFrame(Dict)

	df_picks = pd.read_csv(picks_path)
	df_final = df_picks.merge(df,on='PLAYER',how='left')
	return render_template("pool.html",df_final=df_final)


@app.route('/posts')
def posts():
	url="http://www.espn.com/golf/leaderboard"
	page = requests.get(url)
	doc = lh.fromstring(page.content)
	tr_elements = doc.xpath('//tr')
	#Create empty list
	col=[]
	i=0
	#For each row, store each first element (header) and an empty list
	for t in tr_elements[0]:
		i+=1
		name=t.text_content()
		col.append((name,[]))
	
	#Since out first row is the header, data is stored on the second row onwards
	for j in range(1,len(tr_elements)):
		#T is our j'th row
		T=tr_elements[j]
		#i is the index of our column
		i=0
		#Iterate through each element of the row
		for t in T.iterchildren():
			data=t.text_content() 
			#Check if row is empty
			if i>0:
			#Convert any numerical value to integers
				try:
					data=int(data)
				except:
					pass
			#Append the data to the empty list of the i'th column
			col[i][1].append(data)
			#Increment i for the next column
			i+=1
	
	Dict={title:column for (title,column) in col}
	df=pd.DataFrame(Dict)
	return render_template("players-selected.html",df=df)

# Create a route decorator
@app.route('/')
def index():
	url="http://www.espn.com/golf/leaderboard"
	page = requests.get(url)
	doc = lh.fromstring(page.content)
	tr_elements = doc.xpath('//tr')
	#Create empty list
	col=[]
	i=0
	#For each row, store each first element (header) and an empty list
	for t in tr_elements[0]:
		i+=1
		name=t.text_content()
		col.append((name,[]))
	
	#Since out first row is the header, data is stored on the second row onwards
	for j in range(1,len(tr_elements)):
		#T is our j'th row
		T=tr_elements[j]
		#i is the index of our column
		i=0
		#Iterate through each element of the row
		for t in T.iterchildren():
			data=t.text_content() 
			#Check if row is empty
			if i>0:
			#Convert any numerical value to integers
				try:
					data=int(data)
				except:
					pass
			#Append the data to the empty list of the i'th column
			col[i][1].append(data)
			#Increment i for the next column
			i+=1
	
	Dict={title:column for (title,column) in col}
	df=pd.DataFrame(Dict)
	max_score = df['TOT'].max()
	df_picks = pd.read_csv(picks_path)
	df_final = df_picks.merge(df,on='PLAYER',how='left')
	df_final['TOT'].replace('--',999,inplace=True)
	df_final.dropna(inplace=True)
	df_final['TOT'] = df_final.apply(lambda x: max_score if x['SCORE'] == 'CUT' else x['TOT'], axis=1)
	df_final.sort_values(by=['Team Name','TOT'],ascending=True,inplace=True)
	df_final = df_final.groupby('Team Name').head(TOTAL_GOLFERS_SCORED)
	df_final_two = df_final.groupby('Team Name')['TOT'].sum().reset_index().sort_values(by='TOT',ascending=True)
	df_final_two['Position'] = df_final_two['TOT'].rank(method='min')
	df_final_two.sort_values(by='Position',inplace=True)
	df_final_two['Final Score'] = df_final_two['TOT'] - (TOTAL_GOLFERS_SCORED * round_tracker())
	return render_template("pool-standings.html", df_final=df_final_two)


# Create Custom Error Pages

# Invalid URL
@app.errorhandler(404)
def page_not_found(e):
	return render_template("404.html"), 404

# Internal Server Error
@app.errorhandler(500)
def page_not_found(e):
	return render_template("500.html"), 500

# Create Password Test Page
@app.route('/test_pw', methods=['GET', 'POST'])
def test_pw():
	email = None
	password = None
	pw_to_check = None
	passed = None
	form = PasswordForm()


	# Validate Form
	if form.validate_on_submit():
		email = form.email.data
		password = form.password_hash.data
		# Clear the form
		form.email.data = ''
		form.password_hash.data = ''

		# Lookup User By Email Address
		pw_to_check = Users.query.filter_by(email=email).first()
		
		# Check Hashed Password
		passed = check_password_hash(pw_to_check.password_hash, password)

	return render_template("test_pw.html", 
		email = email,
		password = password,
		pw_to_check = pw_to_check,
		passed = passed,
		form = form)


# Create Name Page
@app.route('/name', methods=['GET', 'POST'])
def name():
	name = None
	form = NamerForm()
	# Validate Form
	if form.validate_on_submit():
		name = form.name.data
		form.name.data = ''
		flash("Form Submitted Successfully!")
		
	return render_template("name.html", 
		name = name,
		form = form)




# Create a Blog Post model
class Posts(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String(255))
	content = db.Column(db.Text)
	#author = db.Column(db.String(255))
	date_posted = db.Column(db.DateTime, default=datetime.utcnow)
	slug = db.Column(db.String(255))
	# Foreign Key To Link Users (refer to primary key of the user)
	poster_id = db.Column(db.Integer, db.ForeignKey('users.id'))

# Create Model
class Users(db.Model, UserMixin):
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(20), nullable=False, unique=True)
	name = db.Column(db.String(200), nullable=False)
	email = db.Column(db.String(120), nullable=False, unique=True)
	favorite_color = db.Column(db.String(120))
	about_author = db.Column(db.Text(), nullable=True)
	date_added = db.Column(db.DateTime, default=datetime.utcnow)
	profile_pic = db.Column(db.String(), nullable=True)

	# Do some password stuff!
	password_hash = db.Column(db.String(128))
	# User Can Have Many Posts 
	posts = db.relationship('Posts', backref='poster')


	@property
	def password(self):
		raise AttributeError('password is not a readable attribute!')

	@password.setter
	def password(self, password):
		self.password_hash = generate_password_hash(password)

	def verify_password(self, password):
		return check_password_hash(self.password_hash, password)

	# Create A String
	def __repr__(self):
		return '<Name %r>' % self.name

