from flask import Flask, render_template, redirect, request, session,flash
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import smtplib,random,string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = 'e521f193d3d30e214b93b4df5d95e67cfc792be10c8edcc5'

# MongoDB setup
app.config['MONGO_URI'] = 'mongodb://localhost:27017/task_manager'
mongo = PyMongo(app)

# Initialize the scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Function to generate OTP
def generate_otp():
    digits = string.digits
    return ''.join(random.choice(digits) for i in range(6))

# Function to send email
def send_email(receiver_email, subject, body):
    sender_email = 'jyothikareads@gmail.com'  # Your email address
    sender_password = 'ayqo gdrj mrps hvvv'  # Your email password

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")


def send_due_date_reminders():
    print("Sending due date reminders...")
    today = datetime.now().date()
    tasks_due_today = mongo.db.tasks.find({'due_date': {'$gte': datetime.combine(today, datetime.min.time()), '$lt': datetime.combine(today + timedelta(days=1), datetime.min.time())}})
    for task in tasks_due_today:
        # Check if the task's due date is today
        task_due_date = task['due_date'].date()
        if task_due_date == today:
            send_task_reminder_email(task)


def send_task_reminder_email(task):
    sender_email = 'jyothikareads@gmail.com'  # Your email address
    sender_password = 'ayqo gdrj mrps hvvv'  # Your email password

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = task['email']
    msg['Subject'] = "Task Reminder"
    body = f"Reminder: Task '{task['name']}' is due today!"
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, task['email'], msg.as_string())
    server.quit()


def send_task_details(task):
    print("Sending task details...")
    sender_email = 'jyothikareads@gmail.com'  # Your email address
    sender_password = 'ayqo gdrj mrps hvvv'  # Your email password

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = task['email']
    msg['Subject'] = "Task Details"
    body = f"Task details:\nName: {task['name']}\nCategory: {task['category']}\nDue Date: {task['due_date']}\nPriority: {task['priority']}"
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, task['email'], msg.as_string())
    server.quit()


# Routes
@app.route('/')
def index():
    if 'username' in session:
        current_date = datetime.now().date()
        tasks = mongo.db.tasks.find({'user_id': session['user_id']})
        sorted_tasks = sorted(tasks, key=lambda x: ('High', 'Medium', 'Low').index(x['priority']))
        for task in sorted_tasks:
            due_date = task['due_date'].date() if isinstance(task['due_date'], datetime) else task['due_date']
            if due_date < current_date:
                task['past_due'] = True
            else:
                task['past_due'] = False
            task['due_date'] = str(due_date)
        categories = mongo.db.categories.find({'user_id': session['user_id']})
        return render_template('index.html', tasks=sorted_tasks, categories=categories, current_date=current_date)
    else:
        return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = mongo.db.users.find_one({'username': username})
        if user and user['password'] == password:
            session['username'] = username
            session['user_id'] = str(user['_id'])
            session['email'] = user['email']  # Store the email in the session
            return redirect('/')
        else:
            return render_template('login.html', error='Invalid username or password')
    else:
        return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect('/login')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        # Check if the username already exists
        if mongo.db.users.find_one({'username': username}):
            error = 'Username already exists'
            return render_template('register.html', error=error)

        # Insert the user details into the database
        user_data = {
            'username': username,
            'password': password,
            'email': email
        }
        mongo.db.users.insert_one(user_data)

        # Redirect to the login page
        return redirect('/login')
    else:
        return render_template('register.html')


@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':
        task_name = request.form['name']
        category = request.form['category']
        due_date_str = request.form['due_date']
        priority = request.form['priority']

        # Convert the due date string to a datetime object
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d')

        # Check if the due date is in the past
        if due_date.date() < datetime.now().date():
            error = 'Past date not accepted'
            categories = mongo.db.categories.find({'user_id': session['user_id']})
            return render_template('add_task.html', error=error, categories=categories)

        # Convert the due date to datetime and set time to midnight
        due_datetime = datetime.combine(due_date, datetime.min.time())

        # Proceed with adding the task if the due date is valid
        task = {
            'name': task_name,
            'category': category,
            'due_date': due_datetime,  # Convert to datetime
            'priority': priority,
            'user_id': session['user_id'],
            'email': session['email']  # Assuming you have a field for user email
        }
        mongo.db.tasks.insert_one(task)

        # Send task details immediately after adding the task
        send_task_details(task)

        # Trigger the function to send reminders for tasks due today
        send_due_date_reminders()

        return redirect('/')
    else:
        categories = mongo.db.categories.find({'user_id': session['user_id']})
        return render_template('add_task.html', categories=categories)


@app.route('/edit_task/<task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if request.method == 'POST':
        edited_task = {
            'name': request.form['name'],
            'category': request.form['category'],
            'due_date': datetime.strptime(request.form['due_date'], '%Y-%m-%d'),
            'priority': request.form['priority'],
            'user_id': session['user_id']
        }
        current_date = datetime.now().date()
        if edited_task['due_date'].date() < current_date:
            return "Past date not accepted"
        else:
            mongo.db.tasks.update_one({'_id': ObjectId(task_id)}, {'$set': edited_task})
            return redirect('/')
    else:
        task = mongo.db.tasks.find_one({'_id': ObjectId(task_id)})
        categories = mongo.db.categories.find({'user_id': session['user_id']})
        task['due_date'] = task['due_date'].strftime('%Y-%m-%d')
        return render_template('edit_task.html', task=task, categories=categories)


@app.route('/delete_task/<task_id>')
def delete_task(task_id):
    mongo.db.tasks.delete_one({'_id': ObjectId(task_id)})
    return redirect('/')


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
    categories = mongo.db.categories.find({'user_id': session['user_id']})
    return render_template('profile.html', user=user, categories=categories)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        # Check if email exists in the database
        user = mongo.db.users.find_one({'email': email})
        if user:
            # Generate OTP
            otp = generate_otp()
            # Store OTP in session along with the email
            session['forgot_password_email'] = email
            session['otp'] = otp
            # Send email with OTP
            subject = 'Forgot Password - OTP'
            body = f'Your OTP for resetting the password is: {otp}'
            send_email(email, subject, body)
            flash('An OTP has been sent to your email address.')
            return redirect('/')
        else:
            flash('Email address not found. Please enter a valid email address.')
            return redirect('/forgot_password')
    return render_template('forgotpassword.html')

if __name__ == '__main__':
    app.run(debug=True)
