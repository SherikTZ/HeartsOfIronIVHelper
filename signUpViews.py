import discord
from discord.ui import Select, Button, View
from discord.ui.select import SelectOption
from discord.ext import commands

import datetime
import sqlite3


from databaseFunctions import (
    checkIfUserAlreadyHasSignUp,
    checkIfUserAlreadyHasUnsign,
    insertNewSignUpAttempt,
    insertNewUnsignAttempt,
    fetchAvailableCountries,
    insertPlayerIfNotExists,
    isCountryMajor,
    checkIfPlayerSignedForOption,
    insertGameRecord,
    checkIfCountryHasController,
    getPrimaryControllerID,
    setPlayerSignUpAttemptsInactive,
)

from discordFunctions import dmAreClosed


class SignupHandler(View):
    """Main view that is added to the message that contains sign up standings.
    Has two buttons that upon calling, create their own views and start a DM interaction.
    """

    def __init__(
        self,
        gameID: str,
        connection: sqlite3.Connection,
        cursor: sqlite3.Cursor,
        bot: commands.Bot,
    ) -> None:
        super().__init__(timeout=None)

        self.gameID = gameID
        self.connection = connection
        self.cursor = cursor
        self.bot = bot

        self.signupButton = Button(style=discord.ButtonStyle.blurple, label="SIGN UP")
        self.signupButton.callback = self.signupCallback
        self.add_item(self.signupButton)

        self.unsignButton = Button(style=discord.ButtonStyle.red, label="UNSIGN")
        self.unsignButton.callback = self.unsignCallback
        self.add_item(self.unsignButton)

    async def signupCallback(self, interaction: discord.Interaction) -> None:
        """
        Callback of a sign up button. Before sending a message with a sign up, multiple things are checked, in order:
        1. If DMs are closed, a message is sent to the user to open the messages and the callback is stopped.
        2. If user has signed up for both first and second option, user is prompted to unsign first.
        3. If user has an active signup attempt, a message is sent to the user to wait for the signup to finish and the callback is stopped.
        4. If the user has been attempting to sign up too frequently, the user is asked to wait for a period of time.
        """

        if await dmAreClosed(interaction.user):
            await interaction.response.send_message(
                "Unfortunately, you cannot sign up for the game because your direct messages are closed. Please, open direct messages first.",
                ephemeral=True,
            )
            return

        firstOption = 1
        secondOption = 2
        signedForFirstOption = checkIfPlayerSignedForOption(
            self.cursor, interaction.user.id, firstOption, self.gameID
        )
        signedForSecondOption = checkIfPlayerSignedForOption(
            self.cursor, interaction.user.id, secondOption, self.gameID
        )

        if signedForFirstOption and signedForSecondOption:
            await interaction.response.send_message(
                "You are already signed up! Please unsign first.", ephemeral=True
            )
            return

        if await self.messageIfUserHasInteraction(interaction):
            return

        if await self.preventSignupSpamming(interaction):
            return

        userView = SignupDirectMessage(
            self.gameID, self.connection, self.cursor, interaction.user, self.bot
        )
        insertNewSignUpAttempt(self.connection, self.cursor, interaction.user.id)

        whatIsCountry = """In order to sing up for the game, first select a country you want to play as. \n
        We highly recommend to select a **minor** nation if you have little to none experience since playing a **major** requires a lot of experience with the game. \n \n"""

        await interaction.user.send(whatIsCountry, view=userView)
        await interaction.response.defer()

    async def unsignCallback(self, interaction: discord.Interaction) -> None:
        """
        Callback of a unsign button. Before sending a message with a unsign, multiple things are checked, in order:
        1. If DMs are closed, a message is sent to the user to open the messages and the callback is stopped.
        2. If user has no sign ups for the current game, a message to sign up first is sent to user and the callback is stopped.
        3. If user has an active unsign attempt, a message is sent to the user to wait for the unsign to finish and the callback is stopped.
        4. If the user has been attempting to unsign too frequently, the user is asked to wait for a period of time.
        """

        if await dmAreClosed(interaction.user):
            await interaction.response.send_message(
                "Unfortunately, you cannot sign up for the game because your direct messages are closed. Please, open direct messages first.",
                ephemeral=True,
            )
            return

        playerSignedCountries = self.cursor.execute(
            "SELECT record_id, name, controller, option FROM game_records JOIN countries USING(country_id) WHERE game_id = ? AND player_id = ? AND is_active = 1",
            (self.gameID, interaction.user.id),
        ).fetchall()
        if len(playerSignedCountries) == 0:
            await interaction.response.send_message(
                "You are not signed up for any country!", ephemeral=True
            )
            return

        if await self.messageIfUserHasInteraction(interaction):
            return

        if await self.preventSignupSpamming(interaction):
            return

        insertNewUnsignAttempt(self.connection, self.cursor, interaction.user.id)
        await interaction.user.send(
            "Select a country to unsign from!",
            view=UnsignView(
                self.gameID, self.connection, interaction.user, playerSignedCountries
            ),
        )
        await interaction.response.defer()

    async def messageIfUserHasInteraction(
        self, interaction: discord.Interaction
    ) -> bool:
        """The method checks whether the user has an active signup or unsign attempt and sends a message if so.
        Returns True if the user has an active attempt, False otherwise."""

        if checkIfUserAlreadyHasSignUp(self.cursor, interaction.user.id):
            await interaction.response.send_message(
                "You already have a signup attempt! Please, finish this one first.",
                ephemeral=True,
            )
            return True
        elif checkIfUserAlreadyHasUnsign(self.cursor, interaction.user.id):
            await interaction.response.send_message(
                "You already have a unsign attempt! Please, finish this one first.",
                ephemeral=True,
            )
            return True
        return False

    def checkIfSignUpTimeout(self, playerID: int) -> datetime.timedelta:
        """Checks if the player has been attempting to sign up too frequently, that is if the time between last three attempts is less that timeoutTime.
        Returns timedelta object with the remaining time if the player has been attempting to sign up too frequently, timedelta object with 0 seconds otherwise.
        """

        timeoutTime = datetime.timedelta(minutes=5)

        self.cursor.execute(
            "SELECT datetime FROM signup_attempts WHERE player_id = ? ORDER BY datetime DESC LIMIT 3;",
            (playerID,),
        )
        signUpAttempts = self.cursor.fetchall()

        if len(signUpAttempts) < 3:
            return datetime.timedelta()

        earlyDate = datetime.datetime.strptime(
            signUpAttempts[2][0], "%Y-%m-%d %H:%M:%S.%f"
        )
        lateDate = datetime.datetime.strptime(
            signUpAttempts[0][0], "%Y-%m-%d %H:%M:%S.%f"
        )

        timeBetweenFirstAndLastAttempt = lateDate - earlyDate

        if timeBetweenFirstAndLastAttempt < timeoutTime:
            remainingTime = timeoutTime - timeBetweenFirstAndLastAttempt
            return remainingTime
        return datetime.timedelta()

    def checkIfUnsignTimeout(self, playerID) -> datetime.timedelta:
        """Checks if the player has been attempting to unsign too frequently, that is if the time between last three attempts is less that timeoutTime.
        Returns timedelta object with the remaining time if the player has been attempting to unsign too frequently, timedelta object with 0 seconds otherwise.
        """

        timeoutTime = datetime.timedelta(minutes=5)

        self.cursor.execute(
            "SELECT datetime FROM unsign_attempts WHERE player_id = ? ORDER BY datetime DESC LIMIT 3;",
            (playerID,),
        )
        unsignAttempts = self.cursor.fetchall()

        if len(unsignAttempts) < 3:
            return datetime.timedelta()

        earlyDate = datetime.datetime.strptime(
            unsignAttempts[2][0], "%Y-%m-%d %H:%M:%S.%f"
        )
        lateDate = datetime.datetime.strptime(
            unsignAttempts[0][0], "%Y-%m-%d %H:%M:%S.%f"
        )

        timeBetweenFirstAndLastAttempt = lateDate - earlyDate

        if timeBetweenFirstAndLastAttempt < timeoutTime:
            remainingTime = timeoutTime - timeBetweenFirstAndLastAttempt
            return remainingTime
        return datetime.timedelta()

    async def preventSignupSpamming(self, interaction: discord.Interaction) -> bool:
        """Checks if the user has been attempting to sign up or unsign too frequently. If so, sends a message to the user and returns True.
        Returns False otherwise."""

        user = interaction.user
        signupTimeout = self.checkIfSignUpTimeout(user.id)

        if signupTimeout > datetime.timedelta():
            minutes, seconds = divmod(signupTimeout.seconds, 60)
            await interaction.response.send_message(
                f"You have {minutes} minutes {seconds} seconds until you can sign up again.",
                ephemeral=True,
            )
            return True

        unsignTimeout = self.checkIfUnsignTimeout(user.id)

        if unsignTimeout > datetime.timedelta():
            minutes, seconds = divmod(unsignTimeout.seconds, 60)
            await interaction.response.send_message(
                f"You have {minutes} minutes {seconds} seconds until you can unsign again.",
                ephemeral=True,
            )
            return True

        return False


class SignupDirectMessage(View):
    """The class represents a view for the signup direct message.
    The view consists of three SelectMenus:
    1. User selects a country.
    2. User selects a controller type.
    3. User selects whether this is the first option or second option.
    """

    def __init__(
        self,
        gameID: str,
        connection: sqlite3.Connection,
        cursor: sqlite3.Cursor,
        user: discord.User,
        bot: commands.Bot,
    ):
        super().__init__(timeout=None)
        self.gameID = gameID

        self.connection = connection
        self.cursor = cursor

        self.selectedCountry = None
        self.controllerType = None
        self.option = None

        self.bot = bot

        self.user = user
        self.discordTag = f"{user.name}#{user.discriminator}"

        insertPlayerIfNotExists(self.cursor, self.user.id, self.discordTag)

        # If player has already signed up for a certain option, the other option is automatically selected.
        firstOption = 1
        self.signedForFirstOption = checkIfPlayerSignedForOption(
            cursor, self.user.id, firstOption, self.gameID
        )
        if self.signedForFirstOption:
            self.option = 2
        secondOption = 2
        self.signedForSecondOption = checkIfPlayerSignedForOption(
            cursor, self.user.id, secondOption, self.gameID
        )

        if self.signedForSecondOption:
            self.option = 1

        # Country SelectMenu
        availableCountries = fetchAvailableCountries(
            self.cursor, self.gameID, self.user.id
        )

        countrySelectOptions = [
            SelectOption(label=option[1], value=option[0], emoji=option[2])
            for option in availableCountries
        ]
        self.countrySelect = Select(
            placeholder="Select a country!", options=countrySelectOptions
        )
        self.countrySelect.callback = self.countrySelectCallback

        # Controller SelectMenu

        self.controllerSelect = Select(
            placeholder="Select a Controller Type",
            options=[
                SelectOption(label="Primary Controller", value=1, emoji="🅿️"),
                SelectOption(
                    label="Secondary Controller (CO-OP)",
                    value="2",
                    emoji="🇸",
                ),
            ],
        )

        self.controllerSelect.callback = self.controllerSelectCallback

        # Option SelectMenu
        self.optionSelect = Select(
            placeholder="Select an option",
            options=[
                SelectOption(label="First Option", value=1, emoji="1️⃣"),
                SelectOption(label="Second Option", value=2, emoji="2️⃣"),
            ],
        )

        self.optionSelect.callback = self.optionSelectCallback

        self.add_item(self.countrySelect)

    def stop(self):
        setPlayerSignUpAttemptsInactive(self.connection, self.cursor, self.user.id)
        super().stop()

    async def countrySelectCallback(self, interaction: discord.Interaction):
        self.selectedCountry = interaction.data["values"][0]
        await self.updateSelect(self.countrySelect, interaction, self.selectedCountry)

        primaryControllerID = 1
        secondaryControllerID = 2
        whatIsController = """**Primary Controller** is the player who is responsible for the main parts of the nation management - strategic planning, template designs, research, etc. \n
    **Secondary Controller (CO-OP)** is the helping player that is reponsible for trading with other countries, micromanaging divisions, or other small tasks. \n
    **Secondary Controller** is only available for **major** countries. \n
    If you are new to the game and want to learn, it is recommended to sign up for the **secondary controller**. \n
    You need to ask the **primary controller** for permission to sign up for the **secondary controller**. \n
    (The bot handles those requests) \n"""

        if not isCountryMajor(self.cursor, self.selectedCountry):
            self.controllerType = 1
            await interaction.user.send(
                "The nation you are signing up is not a major, so you were automatically signed up for the **primary controller.**"
            )
            await self.processOption(interaction)

        elif checkIfCountryHasController(
            self.cursor, self.gameID, self.selectedCountry, primaryControllerID
        ):
            await interaction.user.send(
                "This country already has **primary controller**. In order to sign up for the **secondary controller**, you need confirmation from the primary controller. "
            )

            await interaction.user.send(whatIsController)

            primaryControllerTag = getPrimaryControllerID(
                self.cursor, self.gameID, self.selectedCountry
            )
            primaryController = await self.bot.fetch_user(primaryControllerTag)

            secondaryControllerRequest = SecondaryControllerRequest(
                primaryControllerTag, self.connection
            )
            await primaryController.send(
                f"**{self.discordTag}** wants to be the **secondary controller** for **{self.selectedCountry}**. Do you confirm?",
                view=secondaryControllerRequest,
            )
            await secondaryControllerRequest.wait()

            if secondaryControllerRequest.result:
                self.controllerType = 2
                await self.processOption(interaction)

            else:
                await self.user.send(
                    "Your request for secondary controller was denied."
                )
        elif checkIfCountryHasController(
            self.cursor, self.gameID, self.selectedCountry, secondaryControllerID
        ):
            await interaction.user.send(
                "This country already has **secondary controller**. As such, you were signed for primary controller."
            )

            await interaction.user.send(whatIsController)
            self.controllerType = 1
            await self.processOption(interaction)
        else:
            self.add_item(self.controllerSelect)
            await interaction.user.send("Select a controller type!", view=self)
            await interaction.user.send(whatIsController)

    async def controllerSelectCallback(self, interaction: discord.Interaction) -> None:
        self.controllerType = interaction.data["values"][0]
        await self.updateSelect(self.controllerSelect, interaction, self.controllerType)
        await self.processOption(interaction)

    async def optionSelectCallback(self, interaction: discord.Interaction) -> None:
        self.option = interaction.data["values"][0]
        await self.updateSelect(self.optionSelect, interaction, self.option)
        await interaction.user.send(
            f"Confirming signup for **{self.selectedCountry}** as **{self.controllerType}** for **{self.option}**"
        )
        insertGameRecord(
            self.connection,
            self.cursor,
            self.gameID,
            self.user.id,
            self.selectedCountry,
            self.controllerType,
            self.option,
        )
        self.stop()

    async def automaticOptionSelectionMessage(
        self, interaction: discord.Interaction
    ) -> None:
        """A function that sends a message to the user if they are already signed up for a certain option.\
        If they are signed up for the first option, they are notified about being signed up for the second option and vice versa.
        Used when the option selection menu is not necessary."""

        if self.option == 1:
            await interaction.user.send(
                "You are already signed up for the second option. As such, you were automatically signed for first option.",
            )
        elif self.option == 2:
            await interaction.user.send(
                "You are already signed up for the first option. As such, you were automatically signed for second option.",
            )

    async def processOption(self, interaction: discord.Interaction) -> None:
        """A function that processes option selection. If option has been somehow selected without Option SelectMenu, insert new record into database.
        Otherwise, send an option SelectMenu."""

        whatIsOption = """**First Option** is your primary country selection - the country you want to play the most.\n
        When you sign up for the **first option** you confirm that you are going to fullfill your duties as a controller (**primary** or secondary**) for this country. \n
        However, if for some reason, you were to be moved to a different country, it is likely you are going to end up playing your **Second Option**.\n
        You can only have one **first option** and one **second option**. \n"""

        await interaction.user.send(whatIsOption)

        if self.option is not None:
            await self.automaticOptionSelectionMessage(interaction)
            insertGameRecord(
                self.connection,
                self.cursor,
                self.gameID,
                self.user.id,
                self.selectedCountry,
                self.controllerType,
                self.option,
            )
            self.stop()
            await interaction.user.send(
                f"Confirming signup for **{self.selectedCountry}** as **{self.controllerType}** for **{self.option}**"
            )
        else:
            self.add_item(self.optionSelect)
            await interaction.user.send(
                "Is this your first or second option?", view=self
            )

    async def updateSelect(
        self, select: Select, interaction: discord.Interaction, value: str
    ) -> None:
        """Updates select menu when an option is selected to show the selected option."""
        select.disabled = True
        for option in select.options:
            if int(option.value) == int(value):
                select.placeholder = f"{option.emoji}  {option.label}"
                break
        await interaction.message.edit(view=self)
        self.remove_item(select)
        await interaction.response.defer()


class SecondaryControllerRequest(View):
    def __init__(self, discordTag, connection):
        super().__init__(timeout=None)
        self.connection = connection
        self.cursor = self.connection.cursor()
        self.discordTag = discordTag
        self.result = None

        self.confirmButton = Button(style=discord.ButtonStyle.blurple, label="CONFIRM")
        self.confirmButton.callback = self.confirmButtonCallback
        self.add_item(self.confirmButton)

        self.denyButton = Button(style=discord.ButtonStyle.red, label="DENY")
        self.denyButton.callback = self.denyButtonCallback
        self.add_item(self.denyButton)

    async def confirmButtonCallback(self, interaction: discord.Interaction):
        self.result = True
        self.stop()
        await interaction.response.send_message("Confirmed!", ephemeral=True)
        self.disableButtons()

    async def denyButtonCallback(self, interaction: discord.Interaction):
        self.result = False
        self.stop()
        await interaction.response.send_message("Denied!", ephemeral=True)
        self.disableButtons()

    async def disableButtons(self):
        self.confirmButton.disabled = True
        self.denyButton.disabled = True
        await self.message.edit(view=self)


class UnsignView(View):
    def __init__(self, gameID, connection, user, playerSignedCountries):
        super().__init__(timeout=None)

        self.gameID = gameID
        self.connection = connection
        self.cursor = self.connection.cursor()
        self.user = user

        options = []

        for signedCountry in playerSignedCountries:
            recordID = signedCountry[0]
            countryName = signedCountry[0]
            controllerType = signedCountry[1]
            option = signedCountry[2]

            label = f"{countryName} ({controllerType}) - {option}"
            options.append(SelectOption(label=label, value=recordID))

        self.select = Select(
            placeholder="Select country to unsign",
            options=options,
        )

        self.select.callback = self.selectCallback
        self.add_item(self.select)

    async def selectCallback(self, interaction: discord.Interaction):
        self.cursor.execute(
            "UPDATE game_records SET is_active = 0 WHERE record_id = ?",
            (self.select.values[0],),
        )
        self.connection.commit()
        await self.user.send("You have been unsigned from the game!")

        self.select.disabled = True
        for option in self.select.options:
            if int(option.value) == int(self.select.values[0]):
                self.select.placeholder = option.label
                break
        await interaction.message.edit(view=self)
        await interaction.response.defer()
        self.stop()

    def stop(self):
        self.cursor.execute(
            "UPDATE unsign_attempts SET is_active = 0 WHERE player_id = ?",
            (self.user.id,),
        )
        self.connection.commit()
        super().stop()
