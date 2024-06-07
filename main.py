from collections import UserDict
from datetime import datetime, timedelta
from typing import Callable, Dict
from pickle import dump, load
from sys import argv

debug: bool = False


class Field:
    def __init__(self, value: str):
        self.value = value

    def __str__(self) -> str:
        return str(self.value)


class Name(Field):
    ...


class PhoneError(Exception):
    def __init__(self) -> None:
        super().__init__('Give me a valid phone number, please.')


class Phone(Field):
    def __init__(self, value: str):
        if len(value) != 10 or not value.isdigit():
            raise PhoneError
        super().__init__(value)


class BirthdayError(Exception):
    def __init__(self) -> None:
        super().__init__('Invalid date format. Use DD.MM.YYYY')


class Birthday(Field):
    FORMAT: str = '%d.%m.%Y'

    def __init__(self, value: str):
        try:
            self.value = datetime.strptime(value, self.FORMAT)
        except ValueError:
            raise BirthdayError

    def __str__(self) -> str:
        return self.value.strftime(self.FORMAT) if self.value else 'Unknown'


class RecordError(Exception):
    MESSAGE = 'Give me an existing name, please.'

    def __init__(self) -> None:
        super().__init__(self.MESSAGE)


class Record:
    def __init__(self, name: str) -> None:
        self.name = Name(name)
        self.phones: list[Phone] = []
        self.birthday: Birthday | None = None

    def __str__(self) -> str:
        phones = '; '.join(map(lambda phone: phone.value, self.phones))
        return f'Contact name: {self.name.value}, phones: {phones}'

    def __find(self,
               phone: str,
               get_instance: bool = False
               ) -> int | Phone | None:
        for id, instance in enumerate(self.phones):
            if instance.value == phone:
                return instance if get_instance else id
        return None

    def add_phone(self, phone: str) -> None:
        self.phones.append(Phone(phone))

    def remove_phone(self, phone: str) -> None:
        if (id := self.__find(phone)) is not None:
            del self.phones[id]

    def edit_phone(self, current: str, new: str) -> None:
        if (id := self.__find(current)) is None:
            raise ValueError(f'Phone {current} not found!')
        else:
            self.phones[id] = Phone(new)

    def find_phone(self, phone: str) -> Phone | None:
        return self.__find(phone, True)

    def add_birthday(self, birthday: str) -> None:
        self.birthday = Birthday(birthday)


class AddressBook(UserDict):
    data: Dict[str, Record]

    def add_record(self, record: Record) -> None:
        self.data[record.name.value] = record

    def find(self, name: str) -> Record:
        record = self.data.get(name)

        if record is None:
            raise RecordError

        return record

    def delete(self, name: str) -> None:
        for id, record in self.data.items():
            if record.name.value == name:
                del self.data[id]
                break

    @staticmethod
    def date_to_string(date: datetime) -> str:
        return date.strftime(Birthday.FORMAT)

    @staticmethod
    def find_next_weekday(start_date: datetime, weekday: int) -> datetime:
        days_ahead = weekday - start_date.weekday()

        if days_ahead <= 0:
            days_ahead += 7

        return start_date + timedelta(days=days_ahead)

    @classmethod
    def adjust_for_weekend(cls, birthday: datetime) -> datetime:
        if birthday.weekday() >= 5:
            return cls.find_next_weekday(birthday, 0)
        return birthday

    def get_upcoming_birthdays(self, days: int = 7) -> Dict[str, list[str]]:
        dates: Dict[str, list[str]] = {}
        today = datetime.today()

        for name, record in self.data.items():
            if record.birthday:
                # Birthday this year.
                real = record.birthday.value.replace(year=today.year)

                if real < today:
                    real = real.replace(year=today.year + 1)

                if 0 <= (real - today).days <= days:
                    # Congratulation date.
                    event = self.date_to_string(self.adjust_for_weekend(real))

                    if event not in dates:
                        dates[event] = []

                    dates[event].append(name)

        return dates


def input_error(func: Callable) -> Callable:
    def inner(*args: list, **kwargs: dict):
        try:
            return func(*args, **kwargs)
        except Exception:
            return 'Something went wrong.'

    def add_contact_error(args: list[str], book: AddressBook) -> str:
        try:
            return func(args, book)
        except PhoneError as e:
            return e
        except ValueError:
            return 'Give me a new name and a new phone, please.'

    def change_contact_error(args: list[str], book: AddressBook) -> str:
        try:
            return func(args, book)
        except (PhoneError, RecordError) as e:
            return e
        except ValueError:
            return 'Give me an existing name and a new phone, please.'

    def show_phone_error(args: list[str], book: AddressBook) -> str:
        try:
            return func(args, book)
        except RecordError as e:
            return e
        except IndexError:
            return RecordError.MESSAGE

    def show_all_error(book: AddressBook) -> str:
        try:
            return func(book)
        except ValueError:
            return 'Contacts list is empty.'

    def add_birthday_error(args: list[str], book: AddressBook) -> str:
        try:
            return func(args, book)
        except (BirthdayError, RecordError) as e:
            return e
        except ValueError:
            return 'Give me an existing name and birthday date, please.'

    def show_birthday_error(args: list[str], book: AddressBook) -> str:
        try:
            return func(args, book)
        except (IndexError, RecordError):
            return RecordError.MESSAGE

    def birthdays_error(book: AddressBook) -> str:
        try:
            return func(book)
        except ValueError:
            return 'Birthdays list is empty.'

    HANDLERS: Dict[str, Callable] = {
        'add_contact': add_contact_error,
        'change_contact': change_contact_error,
        'show_phone': show_phone_error,
        'show_all': show_all_error,
        'add_birthday': add_birthday_error,
        'show_birthday': show_birthday_error,
        'birthdays': birthdays_error
    }

    return HANDLERS.get(func.__name__, inner)


@input_error
def parse_input(user_input: str) -> tuple[str]:
    cmd, *args = user_input.split()
    return cmd.strip().lower(), *args


@input_error
def add_contact(args: list[str], book: AddressBook) -> str:
    name, phone, *_ = args

    try:
        book.find(name)
    except RecordError:
        record = Record(name)
        record.add_phone(phone)
        book.add_record(record)
        return 'Contact added.'
    else:
        return 'Contact is already added.'


@input_error
def change_contact(args: list[str], book: AddressBook) -> str:
    name, phone, *_ = args

    record = book.find(name)
    record.edit_phone(record.phones[0].value, phone)

    return 'Contact updated.'


@input_error
def show_phone(args: list[str], book: AddressBook) -> str:
    return str(book.find(args[0]))


def table(left_cell: str, right_cell: str, data: Dict[str, str]) -> str:
    def divider(left: str, right: str, middle: str, cell: str = '═'):
        return left + cell * (longest_left + 2) + middle + cell * \
            (longest_right + 2) + right

    def row() -> str:
        return '║ {} │ {} ║'.format(
            left_cell.ljust(longest_left),
            right_cell.rjust(longest_right))

    longest_left = max([len(left_cell) for left_cell in data.keys()])
    longest_right = max([len(right_cell) for right_cell in data.values()])

    if longest_left < len(left_cell):
        longest_left = len(left_cell)

    if longest_right < len(right_cell):
        longest_right = len(right_cell)

    rows = [divider('╔', '╗', '╤'), row(), divider('╟', '╢', '┼', '─')]

    for left_cell, right_cell in data.items():
        rows.append(row())

    rows.append(divider('╚', '╝', '╧'))

    return '\n'.join(rows)


@input_error
def show_all(book: AddressBook) -> str:
    return table(
        'Full name',
        'Phone number',
        {name: record.phones[0].value for name, record in book.data.items()})


@input_error
def add_birthday(args: list[str], book: AddressBook) -> str:
    name, birthday, *_ = args
    book.find(name).add_birthday(birthday)
    return 'Birthday added.'


@input_error
def show_birthday(args: list[str], book: AddressBook) -> str:
    return str(book.find(args[0]).birthday)


@input_error
def birthdays(book: AddressBook) -> str:
    events = book.get_upcoming_birthdays()

    return table('Date',
                 'Users',
                 {date: ', '.join(names) for date, names in events.items()})


def load_data(filename: str = 'address-book.pkl') -> AddressBook:
    try:
        with open(filename, 'rb') as file:
            data = load(file)

            if isinstance(data, AddressBook):
                if debug:
                    print('Use an existing address book since data from file',
                          filename,
                          'is valid.')

                return data

            if debug:
                print('Create a new address book since data from file',
                      filename,
                      'is not valid.')

            return AddressBook()
    except FileNotFoundError:
        if debug:
            print('Create a new address book since file',
                  filename,
                  'is not found.')

        return AddressBook()


def save_data(book: AddressBook, filename: str = 'address-book.pkl') -> None:
    with open(filename, 'wb') as file:
        dump(book, file)


def main() -> None:
    if len(argv) > 1:
        global debug

        for argument in argv[1:]:
            if argument.lower().find('debug') != -1:
                debug = True
                break

    book = load_data()

    print('Welcome to the assistant bot!')

    while True:
        command, *args = parse_input(input('Enter a command: '))

        match command:
            case 'hello': print('How can I help you?')
            case 'add': print(add_contact(args, book))
            case 'change': print(change_contact(args, book))
            case 'phone': print(show_phone(args, book))
            case 'all': print(show_all(book))
            case 'add-birthday': print(add_birthday(args, book))
            case 'show-birthday': print(show_birthday(args, book))
            case 'birthdays': print(birthdays(book))
            case _ if command in ['close', 'exit']:
                save_data(book)
                print('Good bye!')
                break
            case _: print('Invalid command.')


if __name__ == '__main__':
    main()
