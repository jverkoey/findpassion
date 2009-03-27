#!/usr/bin/python
#
# Copyright 2009 Jeff Verkoeyen.

import twitter
import MySQLdb
import sys
import settings

class Enum(object):
    def __init__(self, names):
        for number, name in enumerate(names):
            setattr(self, name, number)


class StateMachine(object):
    def __init__(self, initial_state):
        self.start_state = initial_state
        self.reset()

    def reset(self):    
        self.state = self.start_state
        self.accum = ''
        self.negation = False
        

try:
    conn = MySQLdb.connect (host = "localhost",
                            user = "findpassion",
                            passwd = "F1nd_P4sS10n456!",
                            db = "findpassion")
except MySQLdb.Error, e:
    print "Error %d: %s" % (e.args[0], e.args[1])
    sys.exit (1)

cursor = conn.cursor()
#cursor.execute("SELECT VERSION()")
#row = cursor.fetchone()
#print "server version:", row[0]

cursor.execute("SELECT value FROM config WHERE name=%s", ('last_reply_id'))
row = cursor.fetchone()
if row is None:
    cursor.execute("INSERT INTO config(name) VALUES(%s)", ('last_reply_id'))
    last_reply_id = None
else:
    last_reply_id = row[0]

# Build up a hash map of existing users.
existing_users = {}
disabled_users = {}
current_users = {}
new_users = {}

def notifyUser(screen_name, message):
    #print "---Ignoring request..."
    print "@"+screen_name+" "+message
    api.PostUpdate("@"+screen_name+" "+message)

def addExistingUser(row):
    user = {
        'id': row[0],
        'screen_name': row[1],
        'available_for_hire': row[2],
        'active': row[3],
        'is_admin': row[4]}
    if row[3]:
        existing_users[row[1]] = user
    else:
        disabled_users[row[1]] = user

cursor.execute("SELECT * FROM followers")
rows = cursor.fetchall()
if len(rows) == 0:
    print "Nobody listed yet"
else:
    #print "Known users:"
    for row in rows:
        addExistingUser(row)

api = twitter.Api(username='findpassion', password='F1nd_P4sS10n123!')
if settings.in_dev:
    api.SetCache(None)
#   F1nd_P4sS10n864!
followers = api.GetFollowers()

if len(followers) == 0:
    print "No followers. How sad."
else:
    # Add all users not currently registered to the new_users map
    for user in followers:
        current_users[user.screen_name] = True
        if user.screen_name not in existing_users:
            new_users[user.screen_name] = user

if len(new_users) > 0:
    print "New users: " + str(len(new_users))
    for screen_name in new_users:
        if screen_name in disabled_users:
            print "Reactivating " + screen_name
            cursor.execute("UPDATE followers SET active=1 WHERE screen_name=%s", (screen_name))
            notifyUser(screen_name, "Welcome back! We've kept your profile safely tucked away.")

            user = disabled_users[screen_name]
            del disabled_users[screen_name]
            existing_users[screen_name] = user
        else:
            print "Adding " + screen_name
            cursor.execute("INSERT INTO followers(screen_name) VALUES(%s)", (screen_name))
            cursor.execute("SELECT * FROM followers WHERE id=%s", (conn.insert_id()))
            addExistingUser(cursor.fetchone())
            notifyUser(screen_name, "Thanks for following, now you can access all the findpassion features!")

newly_deactivated = {}
for screen_name in existing_users:
    if screen_name not in current_users:
        print "Deactivating user "+screen_name
        newly_deactivated[screen_name] = True
        cursor.execute("UPDATE followers SET active=0 WHERE screen_name=%s", (screen_name))
        # The user has stopped following us, so they won't even see this update.
        #notifyUser(screen_name, "Thanks for using findpassion!")

for screen_name in newly_deactivated:
    user = existing_users[screen_name]
    del existing_users[screen_name]
    disabled_users[screen_name] = user

################################
# Cache some statistics

available_users = 0
for screen_name in existing_users:
    available_users += existing_users[screen_name]['available_for_hire']


################################
# Start parsing the tweets


tweets = api.GetReplies(last_reply_id)

if last_reply_id is None:
    last_reply_id = 0

newest_id = last_reply_id

updated_users = {}

def parseCommands(screen_name, commands):
    user = existing_users[screen_name]
    updated_user = user.copy()
    commands = commands.partition(' ')[2].strip().lower().split(' ')

    init = commands[0]

    if init == 'available':
        updated_user['available_for_hire'] = True

    elif init == 'unavailable':    
        updated_user['available_for_hire'] = False

    elif init == 'how' and len(commands) > 1:
        if commands[1].startswith('many'):
            if available_users == 1:
                people = 'person'
                areis = 'is'
            else:
                people = 'people'
                areis = 'are'
            if available_users > 0:
                notifyUser(screen_name, "We currently know "+str(available_users)+" "+people+" who "+areis+" looking for work.")
            else:
                notifyUser(screen_name, "We don't know anyone who's looking for work right now. Are you? Tweet \"@findpassion available\" to let us know.")

    elif init == 'accept' and user['is_admin'] and len(commands) > 1:
        if (commands[1].startswith('job') or commands[1].startswith('occupation')) and len(commands) > 2:
            occupation = ' '.join(commands[2:])
            cursor.execute("SELECT id, legit FROM occupations WHERE name=%s", (occupation))
            occupation_data = cursor.fetchone()

            if occupation_data == None:
                #cursor.execute("INSERT INTO occupations(name, suggested_by, legit) VALUES(%s, %s, 1)", (occupation, user['id']))
                notifyUser(screen_name, "That job doesn't exist.")
            else:
                if occupation_data[1]: # Legit?
                    notifyUser(screen_name, "The job's already legit.")
                else:
                    occupation_id = occupation_data[0]
                    cursor.execute("UPDATE occupations SET legit=1 WHERE id=%s", (occupation_id))
                    cursor.execute("SELECT screen_name FROM votes LEFT JOIN followers on follower = id WHERE occupation = %s", (occupation_id))
                    rows = cursor.fetchall()
                    if len(rows) > 0:
                        for row in rows:
                            if not row[0] == screen_name:
                                notifyUser(row[0], "The job title \""+occupation+"\" is now legit!")
                    notifyUser(screen_name, "The job is now legit.")

    elif init == 'suggest' and len(commands) > 1:
        if (commands[1].startswith('job') or commands[1].startswith('occupation')) and len(commands) > 2:
            occupation = ' '.join(commands[2:])
            print "Suggesting job: "+occupation
            cursor.execute("SELECT id, legit FROM occupations WHERE name=%s", (occupation))
            occupation_data = cursor.fetchone()
            occupation_id = None
            new_job = False

            if occupation_data == None:
                # This occupation doesn't exist; create it.
                cursor.execute("INSERT INTO occupations(name, suggested_by) VALUES(%s, %s)", (occupation, user['id']))
                occupation_id = conn.insert_id()
                notifyUser(screen_name, "Thanks for suggesting a new job! If it's accepted into the list we'll tweet you back.")
                new_job = True
            else:
                occupation_id = occupation_data[0]
                if occupation_data[1]: # Legit?
                    print row[1]
                    notifyUser(screen_name, "That job's already legit.")
                    return

            # At this point we know the job's either new or not legit
            # Check if they've already voted.
            cursor.execute("SELECT follower FROM votes WHERE follower=%s AND occupation=%s", (user['id'], occupation_id))
            vote_exists = cursor.fetchone()
            if vote_exists:
                notifyUser(screen_name, "You've already suggested this job.")
            else:
                cursor.execute("UPDATE occupations SET score=score+1 WHERE id=%s", (occupation_id))
                cursor.execute("INSERT INTO votes(follower, occupation) VALUES(%s, %s)", (user['id'], occupation_id))
                if not new_job:
                    notifyUser(screen_name, "We've jotted down your interest in this occupation, we'll tweet you if it goes live.")

    needs_update = False
    keys_to_update = []
    values_to_update = []
    for key in user:
        if user[key] != updated_user[key]:
            print "  " + key + " '" + str(user[key]) + "' => '" + str(updated_user[key]) + "'"
            needs_update = True
            keys_to_update.append(key)
            values_to_update.append(updated_user[key])
    if needs_update:
        print "Updating " + screen_name + "'s account..."
        sql = "UPDATE followers SET "
        for key in keys_to_update:
            sql += key+"=%s "
        sql += "WHERE id=%s"
        values_to_update.append(user['id'])
        cursor.execute(sql, values_to_update)
        existing_users[screen_name] = updated_user
        updated_users[screen_name] = True

if len(tweets) == 1:
    print str(len(tweets)) + " new tweet"
elif len(tweets) > 1:
    print str(len(tweets)) + " new tweets"
for tweet in reversed(tweets):
    if tweet.user.screen_name in existing_users:
        print tweet.user.screen_name+": " + tweet.text
        parseCommands(tweet.user.screen_name, tweet.text)
    else:
        print "I don't know this person: " + tweet.user.screen_name
    newest_id = tweet.id

for screen_name in updated_users:
    print "Firing off update to "+screen_name
    notifyUser(screen_name, "Cheers! Your account's been updated.")

if newest_id != last_reply_id:
    print "Updating last_reply_id..."
    cursor.execute("UPDATE config SET value=%s WHERE name=%s", (newest_id, 'last_reply_id'))

cursor.close()
conn.close()
