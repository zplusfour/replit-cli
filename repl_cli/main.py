import typer, requests, os, zipfile, glob, shutil, json, sys, time, logging
from pathlib import Path
import snow_pyrepl as pyrepl
from typing import Optional
from replit.database import Database
import getpass
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler

__version__ = "1.2.1"
homedir = Path.home()
homedir = str(homedir).replace("\\", "/")

try:
	__sid__ = open(f"{homedir}/replit-cli/connect.sid", "r").read().strip()
except:
	__sid__ = None

app = typer.Typer()

def get_json(user, replname, sid):
	headers = {
		'Content-Type': 'application/json',
		'connect.sid': sid,
		'X-Requested-With': 'https://replit.com',
		'Origin': 'https://replit.com',
		'User-Agent': 'Mozilla/5.0'
	}
	cookies = {
		"connect.sid": sid
	}
	r = requests.get(f"https://replit.com/data/repls/@{user}/{replname}", headers=headers, cookies=cookies)
	return r.json()['id']

@app.callback()
def callback(ctx: typer.Context):
	cmd = ctx.invoked_subcommand
	listofcmds = ["clone", "env", "pull", "push", "exec", "shell", "run"]
	if cmd in listofcmds:
		if not os.path.exists(f"{homedir}/replit-cli/connect.sid"):
			typer.echo("You have not authenticated with Replit CLI yet. To run that command, first run the following command-\nreplit login --help")
			raise typer.Exit()

@app.command(help="Output the current version for Replit CLI")
def version():
	typer.echo(__version__)

@app.command(help="Clone a Repl's contents to your local machine")
def clone(repl:str=typer.Argument("", help="The URL of the repl which is to be cloned.", show_default=False)):
	if not repl:
		typer.echo("No Repl was provided.")
		return

	user = repl.split("/")[0]
	replname = repl.split("/")[1]
	slug = user + "/" + replname
	sid = __sid__
	zip = requests.get(f"https://replit.com/@{slug}.zip", cookies={"connect.sid": sid})
	f = open(f"{replname}.zip", "wb")
	f.write(zip.content)
	f.close()
	with zipfile.ZipFile(f"{replname}.zip", 'r') as zip_ref:
		zip_ref.extractall(replname)
	os.remove(f"{replname}.zip")
	f = open(f"{replname}/.replitcliconfig", "w")
	r = requests.get(f"https://replit.com/data/repls/@{slug}", cookies={"connect.sid": sid}).json()
	id = r['id']
	print(f"""url=https://replit.com/@{slug}\nid={id}""", file=f)
	f.close()
	typer.echo(f"Cloned Repl {replname} to /{replname}")

@app.command(help="Pull the remote contents of the repl inside the working directory.")
def pull(override:bool=False):
	if override:
		f = open(".replitcliconfig", "r")
		content = f.read()
		f.close()
		url = content.split("=")[1].split("\n")[0]
		sid = __sid__.strip()
		zip = requests.get(f"{url}.zip", cookies={"connect.sid": sid})
		f = open(url.split("/")[-1]+".zip", "wb")
		f.write(zip.content)
		f.close()
		with zipfile.ZipFile(url.split("/")[-1]+".zip", 'r') as zip_ref:
			files = glob.glob("*")
			for file in files:
				if file != url.split("/")[-1]+".zip":
					if not "." in file:
						shutil.rmtree(file)
					else:
						os.remove(file)
			zip_ref.extractall("")
		os.remove(url.split("/")[-1]+".zip")
		name = url.split("/")[-1]
		f = open(f".replitcliconfig", "w")
		slug = url.split("/@")[-1]
		r = requests.get(f"https://replit.com/data/repls/@{slug}", cookies={"connect.sid": sid}).json()
		id = r['id']
		print(f"""url={url}\nid={id}""", file=f)
		f.close()
		f = open(f"connect.sid", "w")
		print(f"""{sid}""", file=f)
		f.close()
	else:
		f = open(".replitcliconfig", "r")
		content = f.read()
		f.close()
		url = content.split("=")[1].split("\n")[0]
		sid = __sid__.strip()
		slug = url.split("/@")[-1]
		zip = requests.get(f"{url}.zip", cookies={"connect.sid": sid})
		f = open(url.split("/")[-1]+".zip", "wb")
		f.write(zip.content)
		f.close()
		with zipfile.ZipFile(url.split("/")[-1]+".zip", 'r') as zip_ref:
			zip_ref.extractall(".temp")
		os.remove(url.split("/")[-1]+".zip")
		files = glob.glob("*")
		files2 = glob.glob(".*")
		for file in files2:
			files.append(file)
		done = []
		for file in files:
			# print(f"FILE/DIR FOUND - {file}")
			if "connect.sid" not in file and ".replitcliconfig" not in file:
				newfile = file
				if "." not in file:
					newfile = file + "/"

				if "." not in newfile:
					filelist = glob.glob(f"{newfile}*")
					for file in filelist:
						files.append(file.replace("\\", "/"))
						file = file.replace("\\", "/")

				if "." in newfile:
					try:
						output = open(f".temp/{newfile}", "r").read()
						f = open(newfile, "w")
						f.write(output)
						f.close()
					except:
						output = None
					done.append(newfile)
		shutil.rmtree(".temp")
	typer.echo(f"Refreshed Local Repl Dir")


@app.command(help="Create a live file watching service to automatically save changes")
def livewatch():
	f = open(".replitcliconfig", "r")
	content = f.read()
	f.close()
	url = content.split("=")[1].split("\n")[0]
	uuid = content.split("=")[-1].strip()
	sid = __sid__.strip()
	slug = url.split("/@")[-1].split("\n")[0].strip()
	user, replname = slug.split("/")[0], slug.split("/")[1]
	data = requests.get(f"https://replit.com/data/repls/@{slug}", cookies={"connect.sid": sid}).json()
	if not data['is_owner']:
		typer.echo("You do not have the correct permissions to write to this repl.")
		return

	key = __sid__.strip()

	def delete_file(filename):
		r = requests.delete("https://replops.coolcodersj.repl.co", data=json.dumps({
			"UUID": uuid,
			"username": user,
			"repl": replname,
			"sid": key,
			"filepath": filename
		}),
		headers = {'Content-type': 'application/json', 'Accept': 'text/plain'})

	def write_file(filename, content):
		r = requests.delete("https://replops.coolcodersj.repl.co", data=json.dumps({
			"UUID": uuid,
			"username": user,
			"repl": replname,
			"sid": key,
			"filepath": filename,
			"content": content
		}),
		headers = {'Content-type': 'application/json', 'Accept': 'text/plain'})

	class Event(LoggingEventHandler):
		def dispatch(self, event):
			path = event.src_path.replace("\\", "/")[2:]
			if str(type(event)) == "<class 'watchdog.events.FileCreatedEvent'>":
				print(f"Created {path}")
				write_file(path, "")
			if str(type(event)) == "<class 'watchdog.events.FileModifiedEvent'>":
				print(f"Modified {path}")
				write_file(path, open(path, "r").read())
			if str(type(event)) == "<class 'watchdog.events.FileMovedEvent'>":
				destPath = event.dest_path.replace("\\\\", "/")[2:]
				print(f"Moved {path} to {destPath}")
				delete_file(path)
				write_file(destPath, open(destPath, "r").read())
			if str(type(event)) == "<class 'watchdog.events.FileDeletedEvent'>":
				print(f"Deleted {path}")
				delete_file(path)

	logging.basicConfig(level=logging.INFO,
						format='%(asctime)s - %(message)s',
						datefmt='%Y-%m-%d %H:%M:%S')
	path = "."
	event_handler = Event()
	observer = Observer()
	observer.schedule(event_handler, path, recursive=True)
	observer.start()
	print("File watching service started....enter ^C to quit. (CTRL + C or CMD + C)")
	try:
		while True:
			time.sleep(1)
	except KeyboardInterrupt:
		observer.stop()
	observer.join()


@app.command(help="Push changes to the server and override remote.")
def push(override:bool=False):
	f = open(".replitcliconfig", "r")
	content = f.read()
	f.close()
	url = content.split("=")[1].split("\n")[0]
	uuid = content.split("=")[-1].strip()
	sid = __sid__.strip()
	slug = url.split("/@")[-1].split("\n")[0].strip()
	user, replname = slug.split("/")[0], slug.split("/")[1]
	data = requests.get(f"https://replit.com/data/repls/@{slug}", cookies={"connect.sid": sid}).json()
	if not data['is_owner']:
		typer.echo("You do not have the correct permissions to write to this repl.")
		return

	key = __sid__.strip()

	if not override:
		files = glob.glob("*")
		files2 = glob.glob(".*")
		for file in files2:
			files.append(file)
		done = []
		noExtFile = False
		for file in files:
			print(f"FILE/DIR FOUND - {file}")
			if "connect.sid" not in file and ".replitcliconfig" not in file:
				newfile = file
				if "." not in file:
					newfile = file + "/"
					filelist = glob.glob(f"{newfile}*")
					if filelist == []:
						noExtFile = True
						newfile = file
					else:
						typer.echo("Found Sub-Files/Dirs")
						for file in filelist:
							files.append(file.replace("\\", "/"))
							file = file.replace("\\", "/")
							typer.echo(f"Appending file {file} to list.")

				if "." in newfile or noExtFile:
					print(f"REFRESHING FILE/DIR ON SERVER - {newfile}")
					r = requests.post("https://replops.coolcodersj.repl.co", data=json.dumps({
						"UUID": uuid,
						"username": user,
						"repl": replname,
						"sid": key,
						"filepath": newfile,
						"content": open(newfile, "r").read()
					}),
					headers = {'Content-type': 'application/json', 'Accept': 'text/plain'})

				done.append(newfile)
				noExtFile = False
		typer.echo("Remote Repl Refreshed Successfully")
	else:
		zip = requests.get(f"{url}.zip", cookies={"connect.sid": sid})
		f = open(url.split("/")[-1]+".zip", "wb")
		f.write(zip.content)
		f.close()
		with zipfile.ZipFile(url.split("/")[-1]+".zip", 'r') as zip_ref:
			zip_ref.extractall(".temp")
		os.remove(url.split("/")[-1]+".zip")
		files = glob.glob(".temp/*")
		files2 = glob.glob(".temp/.*")
		for file in files2:
			files.append(file.replace("\\", "/"))
		done = []
		noExtFile = False
		for file in files:
			file = file.replace("\\", "/")
			if "connect.sid" not in file and ".replitcliconfig" not in file:
				newfile = file
				if "." not in file:
					newfile = file + "/"
					filelist = glob.glob(f"{newfile}*")
					if filelist == []:
						noExtFile = True
						newfile = file
					else:
						for file in filelist:
							files.append(file.replace("\\", "/"))
							file = file.replace("\\", "/")

				if "." in newfile or noExtFile:
					r = requests.delete("https://replops.coolcodersj.repl.co", data=json.dumps({
						"UUID": uuid,
						"username": user,
						"repl": replname,
						"sid": key,
						"filepath": newfile,
					}),
					headers = {'Content-type': 'application/json', 'Accept': 'text/plain'})

				done.append(newfile)
				noExtFile = False
		shutil.rmtree(".temp")
		files = glob.glob("*")
		files2 = glob.glob(".*")
		for file in files2:
			files.append(file)
		done = []
		for file in files:
			print(f"FILE/DIR FOUND - {file}")
			if "connect.sid" not in file and ".replitcliconfig" not in file:
				newfile = file
				if "." not in file:
					newfile = file + "/"

				if "." not in newfile:
					filelist = glob.glob(f"{newfile}*")
					typer.echo("Found Sub-Files/Dirs")
					for file in filelist:
						files.append(file.replace("\\", "/"))
						file = file.replace("\\", "/")
						typer.echo(f"Appending file {file} to list.")

				if "." in newfile:
					print(f"REFRESHING FILE/DIR ON SERVER - {newfile}")
					r = requests.post("https://replops.coolcodersj.repl.co", data=json.dumps({
						"UUID": uuid,
						"username": user,
						"repl": replname,
						"sid": key,
						"filepath": newfile,
						"content": open(newfile, "r").read()
					}),
					headers = {'Content-type': 'application/json', 'Accept': 'text/plain'})

				done.append(newfile)

@app.command(help="Authenticate with Replit CLI.\n\nTo get your SID value, check the cookie named 'connect.sid' when you visit Replit in your browser.")
def login(sid:str=None):
	if sid != None:
		if not os.path.exists(f"{homedir}/replit-cli"):
			os.mkdir(f"{homedir}/replit-cli")
		f = open(f"{homedir}/replit-cli/connect.sid", "w")
		print(f"""{sid}""", file=f)
		f.close()
		typer.echo(f"Your SID value has been set as {sid}")
		return
	username = typer.prompt("Enter your username")
	password = getpass.getpass()
	openconfirm = typer.confirm("Replit Login requires an hcaptcha token. You can retrieve one from https://sjurl.tk/captcha. Would you like to visit this site?")
	if not openconfirm:
		typer.echo("Replit Login has been aborted since you denied access to open the hcaptcha site.")
		return

	typer.launch("https://sjurl.tk/captcha")
	hct = typer.prompt("Please copy the token from the site and enter it here")

	r = requests.get('https://replit.com/~', allow_redirects=False)
	sid = r.cookies.get_dict()['connect.sid']
	r = requests.post("https://replit.com/login",
		data={
			"username": username,
			"password": password,
			"hCaptchaResponse": hct,
				"hCaptchaSiteKey": "473079ba-e99f-4e25-a635-e9b661c7dd3e",
			"teacher": False
		},
		headers={
			"User-Agent": "Mozilla/5.0",
			'X-Requested-With': "Replit CLI",
				"referrer": "https://replit.com"
		},
		cookies={
			"connect.sid": sid
		}
	)
	if not r.status_code == 200:
		typer.echo(f"Error! An unexpected error ocurred: HTTP Status was not 200. Received status was {r.status_code}")
		return

	if not os.path.exists(f"{homedir}/replit-cli"):
		os.mkdir(f"{homedir}/replit-cli")
	f = open(f"{homedir}/replit-cli/connect.sid", "w")
	print(f"""{sid}""", file=f)
	f.close()
	typer.echo(f"Your SID value has been set as {sid}")
	typer.echo(f"You have been logged in as {username}!")

@app.command(help="Run, Stop, or Restart a Repl from your local machine.\nDefault option is run, add the --stop or --restart option to change mode.")
def run(repl:str, run:bool=True, stop:bool=False, restart:bool=False):
	sid = __sid__.strip()

	if stop or restart:
		run = False
	x = 0
	for y in [run, stop, restart]:
		if y:
			x += 1

	if x > 1:
		typer.echo("Command failed due to multiple flags.")
		return
	if not "/" in repl:
		typer.echo("Failed Repl match")
		return

	user = repl.split("/")[0]
	replname = repl.split("/")[1]

	key = __sid__.strip()
	token, url = pyrepl.get_token(user, replname, key)
	id = get_json(user, replname, key)
	client = pyrepl.Client(token, id, url)
	channel = client.open('shellrun2', 'runner')
	if run:
		output = channel.get_output({
			'runMain':{
			}
		})
		output = str(output).replace("[", "").replace("]", "").split(", ")
		output2 = ""
		y = 0
		for x in output:
			if "output" in x: y += 1
			if "output" in x and y == 2: out = output[output.index(x)].split("output: \"")[1].split("\"")[0]; output2 += f"{out}\n"
		output = output2
		output = bytes(output, "utf-8").decode("unicode_escape")
		print(output)
		client.close()
	elif stop:
		output = channel.get_output({
			'clear':{
			}
		})
		output = str(output).replace("[", "").replace("]", "").split(", ")
		output2 = ""
		y = 0
		for x in output:
			if "output" in x: y += 1
			if "output" in x and y == 2: out = output[output.index(x)].split("output: \"")[1].split("\"")[0]; output2 += f"{out}\n"
		output = output2
		output = bytes(output, "utf-8").decode("unicode_escape")
		print(output)
		client.close()
	elif restart:
		channel.get_output({
			'clear':{
			}
		})
		output = channel.get_output({
			'runMain':{
			}
		})
		output = str(output).replace("[", "").replace("]", "").split(", ")
		output2 = ""
		y = 0
		for x in output:
			if "output" in x: y += 1
			if "output" in x and y == 2: out = output[output.index(x)].split("output: \"")[1].split("\"")[0]; output2 += f"{out}\n"
		output = output2
		output = bytes(output, "utf-8").decode("unicode_escape")
		print(output)
		client.close()

@app.command(help="Connect to a bash shell with a remote repl.")
def shell(repl:str):
	user = repl.split("/")[0]
	replname = repl.split("/")[1]

	key = __sid__.strip()
	token, url = pyrepl.get_token(user, replname, key)
	id = get_json(user, replname, key)
	client = pyrepl.Client(token, id, url)
	channel = client.open('exec', 'runner')
	while True:
		x = input("$ ")
		if x == "quitreplitcli()":
			break

		output = channel.get_output({
			"exec": {
				"args": x.split(" ")
			}
		})
		output = str(output).replace("[", "").replace("]", "").split(", ")
		output2 = ""
		y = 0
		for x in output:
			if "output" in x: y += 1
			if "output" in x and y == 1: out = output[output.index(x)].split("output: \"")[1].split("\"")[0]; output2 += f"{out}\n"
		output = output2
		output = bytes(output, "utf-8").decode("unicode_escape")
		print(output)

	client.close()

@app.command(help="Execute a command to run on the remote repl.")
def exec(repl:str, cmd:str):
	user = repl.split("/")[0]
	replname = repl.split("/")[1]

	key = __sid__.strip()
	token, url = pyrepl.get_token(user, replname, key)
	id = get_json(user, replname, key)
	client = pyrepl.Client(token, id, url)
	channel = client.open('exec', 'runner')
	output = channel.get_output({
		"exec": {
			"args": cmd.split(" ")
		}
	})
	output = str(output).replace("[", "").replace("]", "").split(", ")
	output2 = ""
	y = 0
	for x in output:
		if "output" in x: y += 1
		if "output" in x and y == 1: out = output[output.index(x)].split("output: \"")[1].split("\"")[0]; output2 += f"{out}\n"
	output = output2
	output = bytes(output, "utf-8").decode("unicode_escape")
	print(output)
	client.close()

@app.command(help="Interact with the Environment of the Repl of the Current Working Directory.")
def env(contents:bool=True, key:str="", value:str="", delete:str=""):
	f = open(".replitcliconfig", "r")
	content = f.read()
	f.close()
	url = content.split("=")[1].split("\n")[0]
	uuid = content.split("=")[-1].strip()
	sid = __sid__.strip()

	file = ".env"

	zip = requests.get(f"{url}.zip", cookies={"connect.sid": sid})
	f = open(url.split("/")[-1]+".zip", "wb")
	f.write(zip.content)
	f.close()
	with zipfile.ZipFile(url.split("/")[-1]+".zip", 'r') as zip_ref:
		zip_ref.extractall(".tempcache")

	os.remove(url.split("/")[-1]+".zip")
	slug = url.split("/@")[-1]
	r = requests.get(f"https://replit.com/data/repls/@{slug}", cookies={"connect.sid": sid}).json()
	id = r['id']

	user, replname = slug.split("/")[0], slug.split("/")[1]
	data = requests.get(f"https://replit.com/data/repls/@{slug}", cookies={"connect.sid": sid}).json()
	if not data['is_owner']:
		typer.echo("You do not have the correct permissions to write to this repl.")
		return

	key = __sid__.strip()


	if not os.path.exists(f".tempcache/{file}"):
		f = open(f".tempcache/{file}", "x")
		f.close()

	env = {}

	f = open(f".tempcache/{file}", "r")
	for line in f:
		line = line.strip()
		key = line.split("=")[0]
		val = line.split("=")[1]
		env[key] = val
	f.close()

	if contents:
		for key in env:
			val = env[key]
			typer.echo(f"{key} = {val}")

	if delete:
		del env[delete]
		typer.echo(f"Deleted pair with key {delete}.")

	if key and value:
		env[key] = value
		typer.echo(f"The following pair has been added/modified in the environment - {key}={value}")

	shutil.rmtree(".tempcache")
	string = ""
	for var in env:
		val = env[var]
		string += f"{var}={val}\n"

	f = open(".env", "w")
	f.write(string)
	f.close()

	r = requests.post("https://replops.coolcodersj.repl.co", data=json.dumps({
		"UUID": id,
		"username": user,
		"repl": replname,
		"sid": key,
		"filepath": file,
		"content": string
	}),
	headers = {'Content-type': 'application/json', 'Accept': 'text/plain'})

@app.command(help="Edit the Replit DB for a Repl")
def db(url:str, data:bool=False, key:str="", value:str="", delete:str=""):
	print(f"Connecting to Database with URL: {url}")
	db = Database(db_url=url)
	print(db.keys())
	if data:
		for key in db.keys():
			try:
				val = db[key]
				typer.echo(f"{key} = {val}")
			except:
				pass

	if delete:
		try:
			del db[delete]
			typer.echo(f"Deleted pair with key {delete}.")
		except:
			typer.echo("ERR! Key could not be deleted- This is most likely a Replit DB bug.")

	if key and value:
		db[key] = value
		typer.echo(f"The following pair has been added/modified in the environment - {key}={value}")

@app.command(help="Lookup the details for a Replit User")
def user(usr:str):
	r = requests.get(f"https://replit.com/data/profiles/{usr}")
	try:
		r = r.json()
	except:
		typer.echo("ERR! API returned invalid Response. The most common cause for this error is an invalid user.")
		return

	org = r['organization']
	repls = {}
	for repl in r['repls']:
		repls[repl['title']] = f"https://replit.com{repl['url']}"

	name = r['firstName'] + r['lastName']
	bio = r['bio']
	icon = r['icon']['url']
	topLangs = " | ".join(r['topLanguages'])
	if 'hacker' in r:
		hacker = "{Hacker}"
	else:
		hacker = ""

	replstr = ""
	for repl in repls:
		replstr += repl + "\n" + repls[repl] + "\n\n"

	text = f"""
{usr} - {name} {hacker}
{org}
{bio}
----------------------------------
Profile Picture URL - {icon}
Top Languages - {topLangs}
Repls -
{replstr}
	"""
	typer.echo(text)

@app.command()
def pip(operation:str):
	typer.echo(f"Running Operation: {operation}")
	os.system(f"pip {operation}")
	typer.echo("Updating pip config...")
	os.system("pip freeze > requirements.txt")

app()
