# Faker Provider Catalog (Practical, Repo-Oriented)

Primary docs:

- https://faker.readthedocs.io/en/stable/
- https://faker.readthedocs.io/en/stable/providers.html
- https://faker.readthedocs.io/en/stable/providers/baseprovider.html

Provider pages used for this catalog:

- https://faker.readthedocs.io/en/stable/providers/faker.providers.address.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.automotive.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.bank.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.barcode.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.color.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.company.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.credit_card.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.currency.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.date_time.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.doi.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.emoji.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.file.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.geo.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.internet.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.isbn.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.job.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.lorem.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.misc.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.passport.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.person.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.phone_number.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.profile.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.python.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.sbn.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.ssn.html
- https://faker.readthedocs.io/en/stable/providers/faker.providers.user_agent.html

This catalog summarizes standard providers and representative methods so agents can pick
good defaults quickly. For exhaustive, installed-version method lists, run the helper
script in `scripts/list_faker_methods.py`.

## BaseProvider

- Examples:
- `bothify("??##")`
- `lexify("????")`
- `numerify("####")`
- `random_element(["a", "b", "c"])`

## address

- Examples:
- `city()`
- `country()`
- `postcode()`
- `street_address()`

## automotive

- Examples:
- `license_plate()`
- `vin()`

## bank

- Examples:
- `aba()`
- `bank_country()`
- `bban()`
- `iban()`

## barcode

- Examples:
- `ean13()`
- `ean8()`
- `upc_a()`
- `isbn13()`

## color

- Examples:
- `color_name()`
- `hex_color()`
- `rgb_color()`
- `safe_hex_color()`

## company

- Examples:
- `company()`
- `catch_phrase()`
- `bs()`

## credit_card

- Examples:
- `credit_card_number()`
- `credit_card_expire()`
- `credit_card_provider()`
- `credit_card_security_code()`

## currency

- Examples:
- `currency_code()`
- `currency_name()`
- `cryptocurrency()`
- `cryptocurrency_code()`

## date_time

- Examples:
- `date_time()`
- `date_time_between(start_date="-2y", end_date="now")`
- `date_time_this_year()`
- `iso8601()`

## doi

- Examples:
- `doi()`

## emoji

- Examples:
- `emoji()`

## file

- Examples:
- `file_name()`
- `file_path()`
- `mime_type()`
- `file_extension()`

## geo

- Examples:
- `coordinate()`
- `latitude()`
- `longitude()`
- `location_on_land()`

## internet

- Examples:
- `email()`
- `ipv4()`
- `url()`
- `user_name()`

## isbn

- Examples:
- `isbn10()`
- `isbn13()`

## job

- Examples:
- `job()`

## lorem

- Examples:
- `word()`
- `words()`
- `sentence()`
- `paragraph()`
- `text()`

## misc

- Examples:
- `boolean()`
- `binary(length=16)`
- `csv(data_columns=((\"id\", \"name\"),))`
- `json(data_columns=((\"id\", \"name\"),))`

## passport

- Examples:
- `passport_number()`

## person

- Examples:
- `first_name()`
- `last_name()`
- `name()`
- `prefix()`

## phone_number

- Examples:
- `phone_number()`
- `msisdn()`

## profile

- Examples:
- `simple_profile()`
- `profile()`

## python

- Examples:
- `pybool()`
- `pyint()`
- `pyfloat()`
- `pylist(nb_elements=5)`
- `pydict(nb_elements=5)`

## sbn

- Examples:
- `sbn9()`

## ssn

- Examples:
- `ssn()`

## user_agent

- Examples:
- `chrome()`
- `firefox()`
- `safari()`
