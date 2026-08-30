"""Parsing of request parameters and of metadata encoded in uploaded filenames.

Split out of utility.py so these can be imported - and tested - without pulling in
smda, mcrit or the database layer. Nothing here touches Flask globals: each helper
takes the request object as an argument. See issue #88.
"""

import logging
import re


def parse_band_range(request, from_form=False):
    minhash_band_range= 2
    arg_to_value = {
        # deactivate minhash bands
        0: 0,
        # 1: "Fast"
        1: 4,
        # 1: "Standard"
        2: 2,
        # 1: "Complete"
        3: 1
    }
    try:
        if from_form:
            minhash_band_range = int(request.form['minhashBandRange'])
        else:
            minhash_band_range = int(request.args.get('minhashBandRange', "2"))
        minhash_band_range = min(3, minhash_band_range)
        minhash_band_range = max(0, minhash_band_range)
    except Exception:
        minhash_band_range = 2
    minhash_band_range = arg_to_value[minhash_band_range]
    return minhash_band_range


def parse_integer_query_param(request, query_param:str):
    """ Try to find query_param in the request and parse it as int """
    param = None
    try:
        value = request.args.get(query_param)
        if value is not None:
            if value.startswith("0x"):
                param = int(value, 16)
            else:
                param = int(value)
    except Exception:
        pass
    return param

def parse_integer_list_query_param(request, query_param:str):
    """ Try to find query_param in the request and parse it as list of int (no brackets) """
    param = None
    try:
        value = request.args.get(query_param)
        if value is not None and re.match(r"^\d+(?:[\s]*,[\s]*\d+)*$", value):
            param = [int(element.strip()) for element in value.split(',')]
    except Exception:
        pass
    return param


def parse_str_query_param(request, query_param:str):
    """ Try to find query_param in the request and parse it as str """
    param = None
    try:
        param = request.args.get(query_param)
    except Exception:
        pass
    return param


def parse_checkbox_query_param(request, query_param:str):
    """ Try to find query_param in the request and parse it as checkbox """
    param = False
    try:
        value = request.args.get(query_param)
        param = True if isinstance(value, str) and value.lower() in ["on", "true"] else False
    except Exception:
        pass
    return param


def parse_integer_post_param(request, query_param:str):
    """ Try to find query_param in the request and parse it as int """
    param = None
    try:
        value = request.form.get(query_param)
        if value is not None:
            param = int(value)
    except Exception:
        pass
    return param


def parse_checkbox_post_param(request, query_param:str):
    """ Try to find query_param in the request and parse it as checkbox """
    param = False
    try:
        value = request.form.get(query_param)
        param = True if isinstance(value, str) and value.lower() in ["on", "true"] else False
    except Exception:
        pass
    return param


def parse_base_addr_form_param(request):
    """ Try to find the base address the submit/query form carries for a dump or SMDA report

    The field is a free text input, and the dropzone serialises the form by hand, so the
    browser never validates it: an empty or malformed value is ordinary user input rather
    than a broken client. Returns None for anything that is not a plain hexadecimal
    address fitting into 64 bit, so the caller can reject the request instead of guessing
    a base address for a memory dump.
    """
    value = request.form.get('base_addr', '').strip()
    if not re.fullmatch("(0[xX])?[0-9a-fA-F]+", value):
        return None
    base_addr = int(value, 16)
    # anything wider than a 64 bit address space is not an address MCRIT could map
    return base_addr if base_addr <= 0xFFFFFFFFFFFFFFFF else None


def parse_bitness_form_param(request):
    """ Try to find the bitness the submit form carries for a dump or SMDA report

    Neither bitness radio is checked until the user - or the filename probe - picks one,
    and an unchecked radio is simply absent from the serialised form, so a missing value
    is ordinary user input as well. Returns None for anything that is not a bitness MCRIT
    knows.
    """
    value = request.form.get('bitness', '').strip()
    return int(value) if value in ('16', '32', '64') else None


def parseBaseAddrFromFilename(filename):
    # try to infer base addr from filename:
    baddr_match = re.search(re.compile("_0x(?P<base_addr>[0-9a-fA-F]{8,16})"), filename)
    if baddr_match:
        parsed_base_addr = int(baddr_match.group("base_addr"), 16)
        logging.info("Parsed base address from file name: 0x%08x %d", parsed_base_addr, parsed_base_addr)
        return parsed_base_addr
    logging.warning("No base address recognized, using None.")
    return None


def parseBitnessFromFilename(filename):
    # try to infer bitness from filename:
    baddr_match = re.search(re.compile("_0x(?P<base_addr>[0-9a-fA-F]{8,16})"), filename)
    if baddr_match:
        if len(baddr_match.group("base_addr")) > 8:
            logging.info("Parsed bitness from base addr len from file name: %s", filename)
            return 64
        else:
            return 32
    logging.warning("No base address recognized, using None.")
    return None
