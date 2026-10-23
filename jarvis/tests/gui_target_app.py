"""Tiny Tk app used as a real target for GUI tests. Prints its state as JSON when Escape is pressed."""

import json
import sys
import tkinter as tk

root = tk.Tk()
root.geometry("400x200+100+100")
root.configure(bg="#ff0000")
clicks = {"n": 0}
entry = tk.Entry(root, width=30)
entry.place(x=20, y=20, width=360, height=30)  # screen ~ (120..480, 120..150)
button = tk.Button(root, text="Press", command=lambda: clicks.__setitem__("n", clicks["n"] + 1))
button.place(x=20, y=100, width=100, height=40)  # screen ~ (120..220, 200..240)


def finish(_event=None):
    print(json.dumps({"text": entry.get(), "clicks": clicks["n"]}), flush=True)
    root.destroy()


root.bind_all("<Escape>", finish)
root.after(100, lambda: (entry.focus_force(), print("READY", flush=True)))
root.after(30000, finish)
root.mainloop()
sys.exit(0)
