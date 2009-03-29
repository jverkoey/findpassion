#!/usr/bin/python
#
# Copyright 2009 Jeff Verkoeyen.

import twitterbot
import random

class Bot(twitterbot.StandardBot):
    '''The findpassion twitter bot.
    '''
    def __init__(self):
        twitterbot.StandardBot.__init__(self,
            dbuser = "findpassion",
            dbpass = "F1nd_P4sS10n456!",
            dbdb   = "findpassion",
            twituser = 'findpassion',
            twitpass = 'F1nd_P4sS10n123!')


        ################################
        # Cache some statistics

        self.available_users = 0
        for screen_name in self.existing_users:
            self.available_users += self.existing_users[screen_name]['available_for_hire']


    def execute(self):
        tweets = self.getTweets()

        updated_users = {}

        if len(tweets) == 1:
            print str(len(tweets)) + " new tweet"
        elif len(tweets) > 1:
            print str(len(tweets)) + " new tweets"
        for tweet in tweets:
            if tweet.user.screen_name in self.existing_users:
                print tweet.user.screen_name+": " + tweet.text
                self.parseCommands(tweet.user.screen_name, tweet.text)
            else:
                print "I don't know this person: " + tweet.user.screen_name

        for screen_name in updated_users:
            print "Firing off update to "+screen_name
            self.notifyUser(screen_name, "Cheers! Your account's been updated")

        self.commitTweets()


    def parseCommands(self, screen_name, commands):
        user = self.existing_users[screen_name]
        updated_user = user.copy()
        commands = commands.partition(' ')[2].strip().lower().split(' ')

        init = commands[0]

        if init == 'available':
            updated_user['available_for_hire'] = True

        elif init == 'unavailable':
            updated_user['available_for_hire'] = False

        elif init == 'how' and len(commands) > 1:
            if commands[1].startswith('many'):
                if self.available_users == 1:
                    people = 'person'
                    areis = 'is'
                else:
                    people = 'people'
                    areis = 'are'
                if self.available_users > 0:
                    self.notifyUser(screen_name, "We currently know "+str(self.available_users)+" "+people+" who "+areis+" looking for work")
                else:
                    self.notifyUser(screen_name, "We don't know anyone who's looking for work right now. Are you? Tweet \"@findpassion available\" to let us know")

        elif user['is_admin'] and init == 'accept' and len(commands) > 1:
            if commands[1].startswith('class') and len(commands) > 2:
                for class_name in ' '.join(commands[2:]).split(','):
                    print "Accepting class: "+class_name
                    class_name = class_name.strip()
                    self.cursor.execute("SELECT id, legit FROM classes WHERE name=%s", (class_name))
                    class_data = self.cursor.fetchone()

                    if class_data == None:
                        self.cursor.execute("INSERT INTO classes(name, suggested_by, legit) VALUES(%s, %s, 1)", (class_name, user['id']))
                        self.notifyUser(screen_name, class_name+" doesn't exist, but it's now added")
                    else:
                        if class_data[1]: # Legit?
                            self.notifyUser(screen_name, class_name+" is already legit")
                        else:
                            class_id = class_data[0]
                            self.cursor.execute("UPDATE classes SET legit=1 WHERE id=%s", (class_id))
                            self.cursor.execute("SELECT screen_name FROM votes LEFT JOIN followers on follower = id WHERE class = %s", (class_id))
                            rows = self.cursor.fetchall()
                            if len(rows) > 0:
                                for row in rows:
                                    if not row[0] == screen_name:
                                        self.notifyUser(row[0], "\""+class_name+"\" is now legit!")
                            self.notifyUser(screen_name, class_name+" is now legit")

        elif init == 'suggest' and len(commands) > 1:
            if commands[1].startswith('class') and len(commands) > 2:
                for class_name in ' '.join(commands[2:]).split(','):
                    class_name = class_name.strip()
                    print "Suggesting class: "+class_name
                    self.cursor.execute("SELECT id, legit FROM classes WHERE name=%s", (class_name))
                    class_data = self.cursor.fetchone()
                    class_id = None
                    new_class = False

                    if class_data == None:
                        # This class doesn't exist; create it.
                        self.cursor.execute("INSERT INTO classes(name, suggested_by) VALUES(%s, %s)", (class_name, user['id']))
                        class_id = self.conn.insert_id()
                        self.notifyUser(screen_name, "Thanks for suggesting a new class! If it's accepted into the list we'll tweet you back")
                        new_class = True
                    else:
                        class_id = class_data[0]
                        if class_data[1]: # Legit?
                            self.notifyUser(screen_name, class_name+" is already legit")
                            return

                    # At this point we know the class's either new or not legit
                    # Check if they've already voted.
                    self.cursor.execute("SELECT follower FROM votes WHERE follower=%s AND class=%s", (user['id'], class_id))
                    vote_exists = self.cursor.fetchone()
                    if vote_exists:
                        self.notifyUser(screen_name, "You've already suggested this class")
                    else:
                        self.cursor.execute("UPDATE classes SET score=score+1 WHERE id=%s", (class_id))
                        self.cursor.execute("INSERT INTO votes(follower, class) VALUES(%s, %s)", (user['id'], class_id))
                        if not new_class:
                            self.notifyUser(screen_name, "We've jotted down your interest in this class, we'll tweet you if it goes live")

        elif init == 'add' and len(commands) > 1:
            if commands[1].startswith('class') and len(commands) > 2:
                for class_name in ' '.join(commands[2:]).split(','):
                    class_name = class_name.strip()
                    print "Adding class: "+class_name
                    self.cursor.execute("SELECT id, legit FROM classes WHERE name=%s", (class_name))
                    class_data = self.cursor.fetchone()
                    class_id = None

                    if class_data == None:
                        # This class doesn't exist; can't do anything.
                        self.notifyUser(screen_name, "Bummer, this class doesn't exist yet. Suggest it by tweeting @findpassion suggest class class-name")
                        return
                    else:
                        class_id = class_data[0]
                        if not class_data[1]: # Legit?
                            self.notifyUser(screen_name, "This class isn't legit. Show interest in it by tweeting @findpassion suggest class class-name")
                            return

                    # At this point we know the class exists and is legit.
                    # Check if they've already added this class.
                    self.cursor.execute("SELECT follower FROM follower_classes WHERE follower=%s AND class=%s", (user['id'], class_id))
                    link_exists = self.cursor.fetchone()
                    if link_exists:
                        self.notifyUser(screen_name, "You already have "+class_name+" listed")
                    else:
                        self.cursor.execute("INSERT INTO follower_classes(follower, class) VALUES(%s, %s)", (user['id'], class_id))
                        self.notifyUser(screen_name, "We've jotted "+class_name+" down in your profile")

        elif init == 'remove' and len(commands) > 1:
            if commands[1].startswith('class') and len(commands) > 2:
                for class_name in ' '.join(commands[2:]).split(','):
                    class_name = class_name.strip()
                    print "Removing class: "+class_name
                    self.cursor.execute("SELECT id, legit FROM classes WHERE name=%s", (class_name))
                    class_data = self.cursor.fetchone()
                    class_id = None

                    if class_data == None:
                        # This class doesn't exist; can't do anything.
                        self.notifyUser(screen_name, "That class doesn't exist")
                        return
                    else:
                        class_id = class_data[0]

                    # At this point we know the class exists.
                    # Check if they've already added this class.
                    self.cursor.execute("SELECT follower FROM follower_classes WHERE follower=%s AND class=%s", (user['id'], class_id))
                    link_exists = self.cursor.fetchone()
                    if link_exists:
                        self.cursor.execute("DELETE FROM follower_classes WHERE follower=%s AND class=%s", (user['id'], class_id))
                        self.notifyUser(screen_name, "We removed "+class_name+" from your profile")
                    else:
                        self.notifyUser(screen_name, "You don't have "+class_name+" listed")

        elif init == 'find' and len(commands) > 1 or len(commands) >= 1:
            if init == 'find':
                commands = commands[1:]
            for class_name in ' '.join(commands).split(','):
                print "Looking for class: "+class_name
                class_name = class_name.strip()
                self.cursor.execute("SELECT id, legit FROM classes WHERE name=%s", (class_name))
                class_data = self.cursor.fetchone()

                if class_data == None and class_name.endswith('s'):
                    self.cursor.execute("SELECT id, legit FROM classes WHERE name=%s", (class_name[:-1]))
                    class_data = self.cursor.fetchone()

                if class_data == None:
                    self.notifyUser(screen_name, "That class doesn't exist")
                else:
                    if class_data[1]: # Legit?
                        class_id = class_data[0]
                        self.cursor.execute("SELECT screen_name FROM follower_classes LEFT JOIN followers on follower = id WHERE class = %s AND available_for_hire=1", (class_id))
                        rows = self.cursor.fetchall()
                        if len(rows) > 0:
                            not_callee = []
                            for row in rows:
                                if not row[0] == screen_name:
                                    not_callee.append(row[0])
                            if len(not_callee) > 0:
                                random.shuffle(not_callee)
                                self.notifyUser(screen_name, class_name+": @"+' @'.join(not_callee[:4]))
                            else:
                                self.notifyUser(screen_name, "You are currently the only listed person with this class")
                        else:
                            self.notifyUser(screen_name, "No available people with the class "+class_name)



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
            self.cursor.execute(sql, values_to_update)
            self.existing_users[screen_name] = updated_user
            updated_users[screen_name] = True


    def dbToUser(self, row):
        return {
            'id': row[0],
            'screen_name': row[1],
            'available_for_hire': row[2],
            'active': row[3],
            'is_admin': row[4]}

    def printStats(self):
        twitterbot.StandardBot.printStats(self)
        print "Available: "+str(self.available_users)