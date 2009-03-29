#!/usr/bin/python
#
# Copyright 2009 Jeff Verkoeyen.

import sys
import twitter
import MySQLdb
import settings

class StandardBot(object):
    '''A twitter bot.
    '''
    def __init__(self, dbuser, dbpass, dbdb, twituser, twitpass):
        try:
            self.conn = MySQLdb.connect(host = "localhost",
                                        user = dbuser,
                                        passwd = dbpass,
                                        db = dbdb)
        except MySQLdb.Error, e:
            print "Error %d: %s" % (e.args[0], e.args[1])
            sys.exit(1)

        self.cursor = self.conn.cursor()

        self.twituser = twituser
        self.twitpass = twitpass

        #cursor.execute("SELECT VERSION()")
        #row = self.cursor.fetchone()
        #print "server version:", row[0]


        ################################
        # Get the last reply id.

        self.cursor.execute("SELECT value FROM config WHERE name=%s", ('last_reply_id'))
        row = self.cursor.fetchone()
        if row is None:
            self.cursor.execute("INSERT INTO config(name) VALUES(%s)", ('last_reply_id'))
            self.last_reply_id = None
        else:
            self.last_reply_id = row[0]


        ################################
        # Initialize the sets of users.

        self.existing_users = {}
        self.disabled_users = {}
        self.current_users = {}
        self.new_users = {}

        self.updateUserLists()


    def updateUserLists(self):
        ################################
        # Get all existing followers.

        self.cursor.execute("SELECT * FROM followers")
        rows = self.cursor.fetchall()
        if len(rows) == 0:
            print "Nobody listed yet"
        else:
            # This will add the user either to existing_users or disabled_users
            for row in rows:
                user = self.dbToUser(row)
                self.addExistingUser(user, user['screen_name'], user['active'])


        ################################
        # Fetch all of the followers
        # from twitter.

        self.api = twitter.Api(self.twituser, self.twitpass)
        if settings.in_dev:
            self.api.SetCache(None)
        #   F1nd_P4sS10n864!
        self.followers = self.api.GetFollowers()


        ################################
        # Check for new followers

        if len(self.followers) == 0:
            print "No followers. How sad."
        else:
            # Add all users not currently registered to the new_users map
            for user in self.followers:
                self.current_users[user.screen_name] = True
                if user.screen_name not in self.existing_users:
                    self.new_users[user.screen_name] = user


        ################################
        # If we have new followers,
        # add 'em to the db.

        if len(self.new_users) > 0:
            print "New users: " + str(len(self.new_users))
            for screen_name in self.new_users:
                if screen_name in self.disabled_users:
                    print "Reactivating " + screen_name
                    self.cursor.execute("UPDATE followers SET active=1 WHERE screen_name=%s", (screen_name))
                    self.notifyUser(screen_name, "Welcome back! We've kept your profile safely tucked away.")

                    user = self.disabled_users[screen_name]
                    del self.disabled_users[screen_name]
                    self.existing_users[screen_name] = user
                else:
                    print "Adding " + screen_name
                    self.cursor.execute("INSERT INTO followers(screen_name) VALUES(%s)", (screen_name))
                    self.cursor.execute("SELECT * FROM followers WHERE id=%s", (conn.insert_id()))

                    row = self.cursor.fetchone()
                    user = self.dbToUser(row)
                    self.addExistingUser(user, user['screen_name'], user['active'])
                    self.notifyUser(screen_name, "Thanks for following, you can now access all of the findpassion features!")


        ################################
        # Deactivate anyone that's not
        # following anymore

        newly_deactivated = {}
        for screen_name in self.existing_users:
            if screen_name not in self.current_users:
                print "Deactivating user "+screen_name
                newly_deactivated[screen_name] = True
                self.cursor.execute("UPDATE followers SET active=0 WHERE screen_name=%s", (screen_name))
                # The user has stopped following us, so they won't even see this update.
                #notifyUser(screen_name, "Thanks for using findpassion!")

        # We move the users to the disabled map here because
        # we can't remove elements from a map while traversing it
        for screen_name in newly_deactivated:
            user = self.existing_users[screen_name]
            del self.existing_users[screen_name]
            self.disabled_users[screen_name] = user



    def notifyUser(self, screen_name, message):
        print "@"+screen_name+" "+message
        self.api.PostUpdate("@"+screen_name+" "+message)


    def getTweets(self):
        ################################
        # Start parsing the tweets

        tweets = self.api.GetReplies(self.last_reply_id)

        self.newest_id = self.last_reply_id
        # Grab the newest id.
        for tweet in reversed(tweets):
            self.newest_id = tweet.id
        
        return reversed(tweets)

    def commitTweets(self):
        if self.newest_id != self.last_reply_id:
            print "Updating last_reply_id..."
            self.cursor.execute("UPDATE config SET value=%s WHERE name=%s", (self.newest_id, 'last_reply_id'))

        self.cursor.close()
        self.conn.close()


    def addExistingUser(self, user, screen_name, enabled):
        if enabled:
            self.existing_users[screen_name] = user
        else:
            self.disabled_users[screen_name] = user


    def printStats(self):
        print "Existing:  "+str([user for user in self.existing_users])
        print "Disabled:  "+str([user for user in self.disabled_users])
