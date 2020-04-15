from misc_classes import SimpleLogger
from operator import itemgetter
from database import Database
import datetime
import graph
import time
import praw
import json
import re
import os

with open("config.json", "r") as f:
    CONFIG = json.load(f)

REDDIT = praw.Reddit(**CONFIG["redditapi"])
SUBREDDIT = REDDIT.subreddit(CONFIG["subreddit"])
COMMENT_TAIL = CONFIG["comment_tail"]
FREE_FLAIRS = CONFIG["free_flairs"]

db = Database()
simplelogger = SimpleLogger()

def get_time():
    #this is not the correct way to do this but I don't care
    return time.strftime("%b %d %Y %H:%M:%S", time.gmtime())

def display(message):
    message = "%d\t[%s]\t%s" % (os.getpid(), get_time(), message)
    print(message)
    simplelogger.log(message)

def get_lambda_from_flair(s):
    result = re.search("\[(.*)\]", s)
    if result is not None and "Doot Coin" in result.group(1):
        return result.group(1)
    else:
        return ""

def update_users_flair_from_comment(comment):
    #implemented only for legacy
    update_users_flair(str(comment.author))

def update_users_flair(username):
    flairtext = next(SUBREDDIT.flair(redditor=username))["flair_text"]
    if flairtext is None or 'λ' in flairtext:
        flairtext = ""
    else:
        flairscore = get_lambda_from_flair(flairtext)
        flairtext = str(flairtext.replace("[%s] " % flairscore, ""))
    if username in get_mods():
        newflair = "[∞ Doot Coin] %s" % (flairtext)
    else:
        actualscore = db.get_lambda(username)[0]
        newflair = "[%i Doot Coin] %s" % (actualscore, flairtext)
    SUBREDDIT.flair.set(redditor = username, text = newflair)

def get_mods():
    return [str(i) for i in SUBREDDIT.moderator()] + ["AutoModerator"]

def update_tables(scores, data):
    content = ""
    date = str(datetime.date.today())
    mods = get_mods()
    imagepath = graph.make_graph(data)
    bylambda = [i for i in sorted(scores, key = itemgetter(1), reverse = True) if i[0] not in mods][:10]
    byhelps = sorted(scores, key = itemgetter(2), reverse = True)[:10]

    SUBREDDIT.stylesheet.upload("wikigraph", imagepath)

    content += "\n\n##/r/YouTuber_initiative Doot Coin tables: %s" % date

    content += "\n\n###By Doot Coin:"
    content += "\n\nUsername|Doot Coin|Help given\n:--|:--|:--"
    for line in bylambda:
        content += "\n/u/%s|%i|%i" % (line[0], line[1], line[2])

    content += "\n\n###By Help given:"
    content += "\n\nUsername|Doot Coin|Help given\n:--|:--|:--"
    for line in byhelps:
        λ = str(line[1])
        if line[0] in mods:
            λ = "∞"
        content += "\n/u/%s|%s|%i" % (line[0], λ, line[2])

    content += "\n\n![](%%%%wikigraph%%%%)\n\nTotal Doot Coins in circulation|Useful advice given|Unique users\n:--|:--|:--\n%i|%i|%i" % (data[-1][1], data[-1][2], data[-1][3])

    SUBREDDIT.wiki["lambdatables"].edit(content, reason = "Update: %s" % date)
    SUBREDDIT.wiki[date].edit(content, reason = "Update: %s" % date)

    currentdata = SUBREDDIT.wiki["index"].content_md
    currentdata += "\n\n* [%s](/r/YouTuber_Initiative/wiki/%s)" % (date, date)

    SUBREDDIT.wiki["index"].edit(currentdata, reason = "Update: %s" % date)

def every_day():
    display("Updated statistics")
    db.update_stats()
    update_tables(db.get_scores(), db.get_stats())

def handle_mylambda(comment):
    author = str(comment.author)
    λ, links = db.get_lambda(author)
    if author in get_mods():
        text = "/u/%s is a moderator, and therefore has ∞ Doot Coins." % author
    else:
        text = "/u/%s currently has %i Doot Coins, and has helped helping the following posts:" % (author, λ)
        count = 0
        for link in links:
            if "www.reddit.com" not in link:
                link = "https://www.reddit.com" + link

            #set a max limit on the number of times this will iterate to stop it
            #breaking because of Reddit's character limit.
            count += 1
            text += "\n\n- [%s](%s)" % (REDDIT.submission(url = link).title, link)
            if count > 100:  #experminent with this number
                text += "\n\n[%i more...]" % len(links) - count
                break

    update_users_flair_from_comment(comment)
    return text

def handle_givelambda(comment):
    submission = comment.submission
    parentauthour = str(comment.parent().author)
    op = str(comment.author)
    if op == parentauthour:
        text = "You cannot give yourself Doot Coins."
    elif parentauthour == "asylum_bot":
        text = "Please only give Doot Coins to humans."
    elif str(comment.author) in get_mods():
        text = "The moderator /u/%s has given /u/%s 1 Doot Coin. /u/%s now has %i Doot Coins." % (str(comment.author), parentauthour, parentauthour, db.get_lambda(parentauthour)[0] + 1)
        db.give_lambda(parentauthour, submission.permalink) 
        display(text)
    elif submission.link_flair_text in FREE_FLAIRS:
        text = "You cannot give Doot Coins in free posts anymore."
    elif op != str(submission.author):
        text = "Only the OP can give Doot Coins."
    elif db.user_given_lambda(parentauthour, str(submission.permalink)):
        text = "You have already given /u/%s Doot Coins for this submission. Why not give Doot Coins to another user instead?" % parentauthour
    else:
        display("'/u/%s' has given '/u/%s' Doot Coins!" % (op, parentauthour))
        text = "You have given /u/%s 1 Doot Coin. /u/%s now has %i Doot Coins" % (parentauthour, parentauthour, db.get_lambda(parentauthour)[0] + 1)
        
        #bonus lambda giving was removed
        # if not db.link_in_db(submission.permalink) or not db.link_in_db(submission.permalink.replace("https://www.reddit.com", "")):
        #     db.give_lambda(parentauthour, submission.permalink, op)
        #     display("The OP received lambda too!")
        # else:
        db.give_lambda(parentauthour, submission.permalink)
    
    # update_users_flair_from_comment(comment)
    update_users_flair_from_comment(comment.parent())
    return text

def handle_takelambda(comment):
    try:
        splitted = comment.body.split()
        user = splitted[1].replace("/u/", "")
        toremove = int(splitted[2].replace("\\", ""))
        reason = " ".join(splitted[3:])
    
        text = "/u/%s has had %i Doot Coins taken away from them for the reason '%s'. /u/%s now has %i Doot Coins" % (user, toremove, reason, user, db.get_lambda(user)[0] - toremove)
        db.change_lambda(user, -toremove)
        display("A moderator removed %i Doot Coins from /u/%s for the reason '%s'" % (toremove,  user, reason))
    except Exception as e:
        display("{ERROR while removing Doot Coin} %s" % e)
        text = r"An error was encountered. Please use the syntax `!takecoin [user] [how much to remove {integer}] [reason]`" + "\n\nThe error was:\n\n" + str(e)

    update_users_flair(user)
    return text

def handle_refundlambda(comment):
    try:
        splitted = comment.body.split()
        user = splitted[1].replace("/u/", "")
        toadd = int(splitted[2].replace("\\", ""))
        reason = " ".join(splitted[3:])
    
        text = "/u/%s has had %i Doot Coins refunded for the reason '%s'. /u/%s now has %i Doot Coins" % (user, toadd, reason, user, db.get_lambda(user)[0] + toadd)
        db.change_lambda(user, toadd)
        display("A moderator refunded %i Doot Coins from /u/%s for the reason '%s'" % (toadd,  user, reason))
    except Exception as e:
        display("{ERROR while refunding Doot Coins} %s" % e)
        text = r"An error was encountered. Please use the syntax `!refundcoin [user] [how much to add {integer}] [reason]`" + "\n\nThe error was:\n\n" + str(e)

    update_users_flair(user)
    return text

def handle_submission(submission):
    score = db.get_lambda(str(submission.author))[0]
    if submission.link_flair_text in FREE_FLAIRS:
        if "youtube.com" in str(submission.url) or "youtu.be" in str(submission.url):
            text = "Your post has been removed because it has the wrong flair. [Discussion], [Meta] and [Collab] flairs are only for text submissions."
            submission.mod.remove()
            display("/u/%s had their submission removed for using the wrong flair." % submission.author)
        else:
            text = "Your post is a discussion, meta or collab post so it costs 0 Doot Coin."
    else:
        if score < 3:
            text = """Thank you for submitting to /r/YouTuber_Initiative. Unfortunally, you submission has been removed since you do not have enough Doot Coins. You need
            3 Doot Coins to post. You currently have %i Doot Coins.""" % score
            submission.mod.remove()
            display("/u/%s had their submission removed for insufficient Doot Coin" % submission.author)
        else:
            text = """Thank you for submitting to /r/YouTuber_Initiative. You have spent 3 Doot Coins to submit here, making your current balance %i Doot Coins.
            /u/%s, please comment `!givecoin` to the most helpful advice you are given. 
            """ % (score - 3, str(submission.author))
            db.change_lambda(str(submission.author), -3)

    update_users_flair(str(submission.author))
    return text

def main():
    comment_stream = SUBREDDIT.stream.comments(pause_after=-1)
    submission_stream = SUBREDDIT.stream.submissions(pause_after=-1)

    while True:
        try:
            for comment in comment_stream:
                if comment is None:
                    break
                if not db.id_in_blacklist(comment.id):
                    db.add_to_blacklist(comment.id)

                    response = None
                    if "!mycoin" in comment.body.lower() and str(comment.author) != "asylum_bot":
                        response = handle_mylambda(comment)

                    if "!givecoin" in comment.body.lower() and str(comment.author) != "asylum_bot":
                        response = handle_givelambda(comment)        

                    if comment.body.startswith("!takecoin") and str(comment.author) in get_mods():
                        response = handle_takelambda(comment)

                    if comment.body.startswith("!refundcoin") and str(comment.author) in get_mods():
                        response = handle_refundlambda(comment)

                    if response is not None:
                        reply = comment.reply(response + COMMENT_TAIL)
                        reply.mod.distinguish(sticky = False)

            for submission in submission_stream:
                if submission is None:
                    break
                if not db.id_in_blacklist(submission.id):
                    db.add_to_blacklist(submission.id)                         
                    display("There has been a new submission: '%s', with flair '%s'" % (submission.title, submission.link_flair_text))

                    response = None
                    if str(submission.author) not in get_mods():
                        response = handle_submission(submission)
                        reply = submission.reply(response + COMMENT_TAIL)
                        reply.mod.distinguish(sticky = True)
                        reply.mod.approve()

        except Exception as e:
            display("{ERROR} %s" % e)
            continue

if __name__ == "__main__":
    file = open("pid.txt", "w")
    file.write(str(os.getpid()))
    file.close()

    # logging.basicConfig(filename = "api.log", format = "[%(asctime)s] %(process)d\t%(message)s", level = logging.DEBUG)

    display("\n####################\n[%s] RESTARTED\n####################\n" % get_time())
    main()

