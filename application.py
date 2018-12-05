import os, datetime
from pytz import timezone

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("postgres://gqesihurzbthsn:30e88c55db5221862b567e0d294d599b7bd2066f2dfe62ba7911d059d802a878@ec2-184-72-239-186.compute-1.amazonaws.com:5432/dbr1rej9mc50n8")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # ensures that all registrant info has been entered correctly
        if not request.form.get("username"):
            return apology("Missing username!")
        elif not request.form.get("password"):
            return apology("Missing password!")
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("Passwords must match!")

        # changes password to hash
        hash_password = generate_password_hash(request.form.get("password"))

        # if possible, stores unique user with his/her hash password to database
        success = db.execute("INSERT INTO users (username,hash) VALUES(:username, :hash_password)",
                             username=request.form.get("username"), hash_password=hash_password)

        # checks if username is unique
        if not success:
            return apology("That username is already taken")

        # logs user in after registering
        registrant = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        session["user_id"] = registrant[0]["id"]

        # redirects user to main page
        return redirect("/")

    return render_template("register.html")


@app.route("/", methods=["GET", "POST"])
@login_required
def index():

    # selects all groups created and orders them alphabetically by subject
    groups = db.execute("SELECT * FROM groups ORDER BY subject")

    # stores each group's info in a list to later be displayed as a table on the index webpage
    rows = []

    # gets information of each available group, storing each info in a dict that will be appended to the rows list
    for group in groups:

        # gets current timezone of Cambridge
        # code inspired by https://stackoverflow.com/questions/11710469/how-to-get-python-to-display-current-time-eastern
        tz = timezone('EST')

        # stores current datetime in format similar to what is stored for each study group in database
        # code inspired by https://stackoverflow.com/questions/7999935/python-datetime-to-string-without-microsecond-component
        current_time = datetime.datetime.now(tz).strftime("%Y-%m-%dT%H:%M")

        # removes any study groups that have already passed their end time
        if current_time >= group['end']:
            db.execute("DELETE FROM joined WHERE group_id = :group_id", group_id=group['id'])
            db.execute("DELETE FROM groups WHERE id = :group_id", group_id=group['id'])

        # prevents groups that are currently full from being displayed
        elif group['occupancy'] != group['people']:

            cells = {}

            # gets the username of the creator of this group
            creator = db.execute("SELECT username FROM users WHERE id = :creator_id", creator_id=group['creator_id'])

            # puts each of the info to be displayed in the index table in a dict so they are readily accessible
            cells["name"] = group['name']
            cells["creator"] = creator[0]['username']
            cells["subject"] = group['subject']
            cells["location"] = group['location']
            cells["occupancy"] = group['occupancy']
            cells["people"] = group['people']
            # formats datetime for start and end times as 'YYYY-MM-DD at HH:MM' to look cleaner
            cells["start"] = str(group['start'])[:10] + " at " + str(group['start'])[11:16]
            cells["end"] = str(group['end'])[:10] + " at " + str(group['end'])[11:16]

            rows.append(cells)

    # allows users to join a group they see displayed on the index webpage
    if request.method == "POST":

        # remembers user's id
        current = session["user_id"]

        # gets group user wants to join
        join_group = request.form.get("join_group")

        # checks if user has selected a group to join
        if not join_group:
            return apology("Please select a group to join")

        # checks to see if user is not already in a group and can join this chosen group, and then lets him/her join
        group_info = db.execute("SELECT id FROM groups WHERE name = :name", name=join_group)
        success = db.execute("INSERT INTO joined (member_id, group_id) VALUES(:member_id, :group_id)", member_id=current, group_id=group_info[0]['id'])
        if not success:
            return apology("Sorry, you are already in a group")

        # increases the amount of people who have joined the group by 1
        db.execute("UPDATE groups SET occupancy = occupancy + 1 WHERE name = :name", name=join_group)

        # records user joining the group in history
        db.execute("INSERT INTO history (member_id, group_name, action) VALUES(:member_id, :group_name, :action)",
                    member_id=current, group_name=join_group, action="Joined")

        return redirect("/joined")

    return render_template("index.html", rows=rows)


@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """Allows usrs to create new study groups"""

    if request.method == "POST":

        # remembers user's id
        current = session["user_id"]

        # stores information entered by the user on the form into variables
        name = request.form.get("name")
        people = request.form.get("people")
        subject = request.form.get("subject")
        location = request.form.get("location")
        start = request.form.get("start")
        end = request.form.get("end")


        # checks if name has been entered properly
        if not name:
            return apology("Missing name of group")

        # checks if integer has been entered for number of people for study group
        try:
            int(people)
        except ValueError:
            return apology("Invalid amount of people")

        # checks if subject has been entered
        if not subject:
            return apology("Missing subject for group")

        # checks if location has been entered
        if not location:
            return apology("Missing location for group")

        #checks if valid number of people for study group has been entered
        if int(people) < 2 or int(people) > 99:
            return apology("Choose a number between 2 and 99 inclusive")

        #checks if valid number of people for study group has been entered
        if start >= end:
            return apology("Your start time must be before your end time")

        # checks if group name already exists
        duplicate = db.execute("SELECT id FROM groups WHERE name = :name", name=name)
        if duplicate:
            return apology("Sorry that group name is already taken")

        # prevents users from creating groups when already in one
        committed = db.execute("SELECT id FROM joined WHERE member_id = :member_id", member_id=current)
        if committed:
            return apology("Sorry, you cannot create a group when you are already in one")

        # allows user to input other location
        if location == "Other":
            location = request.form.get("other")

        # adds study group to database
        db.execute("INSERT INTO groups (creator_id, name, people, subject, location, start, end) VALUES(:creator_id, :name, :people, :subject, :location, :start, :end)",
                    creator_id=current, name=name, people=int(people), subject=subject, location=location, start=start, end=end)

        # gets id of newly created study group
        group_id = db.execute("SELECT id FROM groups WHERE name = :name", name=name)

        # has user join group he/she created
        db.execute("INSERT INTO joined (member_id, group_id) VALUES(:member_id, :group_id)", member_id=current, group_id=group_id[0]['id'])

        # records user creating the group in history
        db.execute("INSERT INTO history (member_id, group_name, action) VALUES(:member_id, :group_name, :action)",
                    member_id=current, group_name=name, action="Created")

        return redirect("/congratulations")

    return render_template("create.html")


@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    """Lets users search for study groups with certain qualities"""

    if request.method == "POST":

        # gets what the user is searching for and makes it case-insensitive
        search = request.form.get("search").lower()

        # selects info of all groups currently created
        groups = db.execute("SELECT * FROM groups ORDER BY subject")

        rows = []

        # iterates through each group
        for group in groups:

            cells = {}

            # gets the username of the creator of this group
            creator = db.execute("SELECT username FROM users WHERE id = :creator_id", creator_id=group['creator_id'])

            # checks if this group has the characterisitcs the user is looking for, and then puts in a dict and appends it to rows list to be displayed if it does
            if search in group['name'].lower() or search in creator[0]['username'].lower() or search in group['subject'].lower() or search in group['location'].lower():
                cells["name"] = group['name']
                cells["creator"] = creator[0]['username']
                cells["subject"] = group['subject']
                cells["location"] = group['location']
                cells["occupancy"] = group['occupancy']
                cells["people"] = group['people']
                cells["start"] = group['start']
                cells["end"] = group['end']

                rows.append(cells)

        return render_template("searched.html", rows=rows)

    return render_template("search.html")

@app.route("/congratulations")
@login_required
def congratulations():
    """Lets user know that their group has been successfully created"""

    return render_template("congratulations.html")


@app.route("/joined", methods=["GET", "POST"])
@login_required
def joined():
    """Shows if user is currently in a study group, and allows them to leave it"""

    # remembers user's id
    current = session["user_id"]

    # checks if user is currently in a group
    committed = db.execute("SELECT group_id FROM joined WHERE member_id = :member_id", member_id=current)

    # placeholders in case user is not currently in a group
    name = "N/A"
    creator = "N/A"
    subject = "N/A"
    location = "N/A"
    members = "N/A"

    # if the user is in a group, this displays relevant info of his/her study group
    if committed:
        group = db.execute("SELECT * FROM groups WHERE id = :group_id", group_id=committed[0]['group_id'])
        creator = db.execute("SELECT username FROM users WHERE id = :creator_id", creator_id=group[0]['creator_id'])
        name = group[0]['name']
        creator = creator[0]['username']
        subject = group[0]['subject']
        location = group[0]['location']
        members = str(group[0]['occupancy']) + " / " + str(group[0]['people'])

    # allows users to leave current group
    if request.method == "POST":

        # checks if user is in a group to leave
        if not committed:
            return apology("You must be in a group to leave one")

        # records user leaving the group in history
        db.execute("INSERT INTO history (member_id, group_name, action) VALUES(:member_id, :group_name, :action)",
                    member_id=current, group_name=name, action="Left")

        # Subtracts one member from the group when the user leaves
        db.execute("UPDATE groups SET occupancy = occupancy - 1 WHERE id = :group_id", group_id=committed[0]['group_id'])

        # deletes any groups with 0 members in it
        members = db.execute("SELECT occupancy FROM groups WHERE id = :group_id", group_id=committed[0]['group_id'])
        if members[0]['occupancy'] == 0:
            db.execute("DELETE FROM groups WHERE id = :group_id", group_id=committed[0]['group_id'])

        # removes group from user's joined list, making him/her free to join other groups
        db.execute("DELETE FROM joined WHERE member_id = :member_id", member_id=current)

        return redirect("/joined")

    return render_template("joined.html", name=name, creator=creator, subject=subject, location=location, members=members)


@app.route("/complete_history")
@login_required
def complete_history():
    """Shows complete history of groups user has created, joined, or left"""

    # remembers user's id
    current = session["user_id"]

    # selects information about what groups the user has joined/left/created
    groups = db.execute("SELECT * FROM history WHERE member_id = :member_id", member_id=current)

    rows = []

    # iterates through each group in user's history
    for group in groups:

        cells = {}

        # puts each of the info to be displayed in the history table in a dict so they are readily accessible
        cells["name"] =  group['group_name']
        cells["action"] = group['action']
        cells["timestamp"] = group['timestamp']

        rows.append(cells)

    return render_template("history.html", rows=rows)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
