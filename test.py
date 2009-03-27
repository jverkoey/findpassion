#!/usr/bin/python
#
# Copyright 2009 Jeff Verkoeyen.

import twitter
import MySQLdb
import sys

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
    api.PostUpdate("@"+screen_name+" "+message)

def addExistingUser(row):
    user = {
        'id': row[0],
        'screen_name': row[1],
        'available_for_hire': row[2]}
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
#api.SetCache(None)
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

tweets = api.GetReplies(last_reply_id)

if last_reply_id is None:
    last_reply_id = 0

newest_id = last_reply_id

updated_users = {}

def parseCommands(screen_name, commands):
    user = existing_users[screen_name]
    updated_user = user.copy()
    commands = commands.partition(' ')[2].strip().lower().split(' ')
    print screen_name + ":"
    negation = False
    for command in commands:
        print "  " + command
        if command == 'available':
            updated_user['available_for_hire'] = not negation
            negation = False
        elif command == 'unavailable':
            updated_user['available_for_hire'] = negation
            negation = False
        elif command == 'not':
            negation = not negation

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
else:
    print str(len(tweets)) + " new tweets"
for tweet in tweets:
    if tweet.user.screen_name in existing_users:
        parseCommands(tweet.user.screen_name, tweet.text)
    else:
        print "I don't know this person: " + tweet.user.screen_name
    newest_id = max(newest_id, tweet.id)

for screen_name in updated_users:
    print "Firing off update to "+screen_name
    notifyUser(screen_name, "Cheers! Your account's been updated.")

if newest_id != last_reply_id:
    print "Updating last_reply_id..."
    cursor.execute("UPDATE config SET value=%s WHERE name=%s", (newest_id, 'last_reply_id'))

cursor.close()
conn.close()
