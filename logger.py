from termcolor import colored

def memory(message: str):
    print(colored("[Memory] "+ message, "yellow"))

def thought(message: str):
    print(colored("[Thought] "+ message, "green"))

def action(message: str):
    print(colored("[Action] "+ message, "blue"))


def system(message: str):
    print(colored( message, "cyan"))

def error(message: str):
    print(colored("[Error] "+ message, "red"))