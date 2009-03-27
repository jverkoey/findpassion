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
cursor.execute("SELECT VERSION()")
row = cursor.fetchone()
print "server version:", row[0]

cursor.execute("SELECT value FROM config WHERE name=%s", ('last_reply_id'))
rows = cursor.fetchall()
if len(rows) == 0:
    cursor.execute("INSERT INTO config(name) VALUES(%s)", ('last_reply_id'))
    last_reply_id = None
else:
    last_reply_id = rows[0][0]

# Build up a hash map of existing users.
existing_users = {}
new_users = {}

cursor.execute("SELECT id, screen_name FROM followers")
rows = cursor.fetchall()
if len(rows) == 0:
    print "Nobody listed yet"
else:
    #print "Known users:"
    for row in rows:
        existing_users[row[1]] = {'id': row[0], 'screen_name': row[1]}
        #print "%s" % (row[1])

api = twitter.Api(username='findpassion', password='F1nd_P4sS10n123!')
#   F1nd_P4sS10n864!
followers = api.GetFollowers()

if len(followers) == 0:
    print "No followers. How sad."
else:
    for user in followers:
        if not user.screen_name in existing_users:
            new_users[user.screen_name] = user

if len(new_users) > 0:
    print "New users: " + str(len(new_users))
    for screen_name in new_users:
        print screen_name
        cursor.execute("INSERT INTO followers(screen_name) VALUES(%s)", (screen_name))
        existing_users[screen_name] = {'id': conn.insert_id(), 'screen_name': screen_name}

print

tweets = api.GetReplies(last_reply_id)

if last_reply_id is None:
    last_reply_id = 0

newest_id = last_reply_id

if len(tweets) == 1:
    print str(len(tweets)) + " new tweet"
else:
    print str(len(tweets)) + " new tweets"
for tweet in tweets:
    newest_id = max(newest_id, tweet.id)

if newest_id != last_reply_id:
    print "Updating last_reply_id..."
    cursor.execute("UPDATE config SET value=%s WHERE name=%s", (newest_id, 'last_reply_id'))

cursor.close()
conn.close()
