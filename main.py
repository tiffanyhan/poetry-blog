#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
from string import letters
import re

import webapp2
import jinja2
import time
import hashlib

import random
import string

from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
								autoescape = True)

def render_str(template, **params):
	print('render string called')
	t = jinja_env.get_template(template)
	return t.render(params)

class Handler(webapp2.RequestHandler):
	def write(self, *a, **kw):
		self.response.write(*a, **kw)

	def render_str(self, template, **params):
		t = jinja_env.get_template(template)
		return t.render(params)

	def render(self, template, **kw):
		self.write(self.render_str(template, **kw))

def blog_key(name = 'default'):
	return db.Key.from_path('/', name)

class Submission(db.Model):
	subject = db.StringProperty(required = True)
	content = db.TextProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)

	def render(self):
		print('render called')
		self._render_text = self.content.replace('\n', '<br>')
		return render_str('submission.html', submission=self)

class MainHandler(Handler):
	def get(self):
		submissions = db.GqlQuery("SELECT * from Submission ORDER BY created DESC limit 10")
		self.render("main.html", submissions=submissions)

class NewHandler(Handler):
	def get(self):
		self.render("new.html")

	def post(self):
		subject = self.request.get("subject")
		content = self.request.get("content")

		if subject and content:
			submission = Submission(parent=blog_key(), subject=subject, content=content)
			submission.put()
			time.sleep(1)

			self.redirect('/%s' % str(submission.key().id()))

		else:
			error = "You must enter both a subject and content"
			self.render("new.html", subject=subject, content=content, error=error)

class SubmissionHandler(Handler):
	def get(self, submission_id):
		key = db.Key.from_path('Submission', int(submission_id), parent=blog_key())
		submission = db.get(key)

		if not submission:
			self.error(404)
			return

		self.render("permalink.html", submission=submission)

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
	return username and USER_RE.match(username)

PASSWORD_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
	return password and PASSWORD_RE.match(password)

EMAIL_RE = re.compile(r"^[\S]+@[\S]+.[\S]+$")
def valid_email(email):
	return not email or EMAIL_RE.match(email)

def unique_username(username):
	q = db.GqlQuery("SELECT * FROM User WHERE username = :1", username)
	users_with_name = q.get()
	return users_with_name == None

def make_salt():
	return ''.join(random.choice(string.letters) for x in xrange(5))

def make_pw_hash(name, pw, salt=''):
	if not salt:
		salt = make_salt()
	h = hashlib.sha256(name + pw + salt).hexdigest()
	return '%s|%s' % (salt, h)

def user_key(name = 'default'):
	return db.Key.from_path('/', name)

class User(db.Model):
	username = db.StringProperty(required = True)
	password = db.StringProperty(required = True)
	email = db.StringProperty()

class SignUpHandler(Handler):
	def get(self):
		self.render("signup.html")

	def post(self):
		have_error = False

		username = self.request.get("username").encode("latin-1")
		password = self.request.get("password").encode("latin-1")
		verify = self.request.get("verify").encode("latin-1")
		email = self.request.get("email").encode("latin-1")

		params = dict(username = username,
					  email = email)

		# check for any errors
		if not valid_username(username):
			params['username_error'] = "That's not a valid username"
			have_error = True
		elif not unique_username(username):
			params['username_error'] = 'That username already exists'
			have_error = True

		if not valid_password(password):
			params['password_error'] = "That's not a valid password"
			have_error = True
		elif password != verify:
			params['verify_error'] = "Your passwords don't match"

		if not valid_email(email):
			params['email_error'] = "That's not a valid email"
			have_error = True

		# there's some error(s)
		if have_error:
			self.render("signup.html", **params)
		# succest!!
		else:
			password_hash = make_pw_hash(username, password)
			user = User(parent=user_key(), username=username, password=password_hash, email=email)
			user.put()
			self.response.headers.add_header('Set-Cookie', 'user-id=%s' % str(user.key().id()))
			time.sleep(1)

			self.redirect('/signup/thanks')

class SignUpThanksHandler(Handler):
	def get(self):
		user_id = self.request.cookies.get('user-id')
		key = db.Key.from_path('User', int(user_id), parent=user_key())
		user = db.get(key)

		if not user:
			self.error(404)
			return

		self.render("signup_thanks.html", user=user)

app = webapp2.WSGIApplication([
	('/', MainHandler),
	('/newpost', NewHandler),
	('/([0-9]+)', SubmissionHandler),
	('/signup', SignUpHandler),
	('/signup/thanks', SignUpThanksHandler)
], debug=True)
