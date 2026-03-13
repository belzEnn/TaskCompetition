import customtkinter as ctk 

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        #створюємо вікно 800 на 600, з назвою "Task Competition"
        self.geometry("800x600")
        self.title("Task Competion")
        self.user1Frame()
        self.user2Frame()
    def user1Frame(self):
        self.user1Frame = ctk.CTkFrame(self, width=390)
        self.user1Label = ctk.CTkLabel(master=self.user1Frame, text="User1", font=("Inter", 15, "bold"))
        self.user1Label.pack()
        self.user1Frame.pack(side="left", fill="both", padx=5, expand=True)

    def user2Frame(self):
        self.user2Frame = ctk.CTkFrame(self, width=390)
        self.user2Frame.pack(side="right", fill="y", padx=5, expand=True)
win = App()
win.mainloop()