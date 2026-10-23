# pygame_test.py EFX stepping patch

The generated `efx.json` now uses a 128-slot display array where the array index is the
actual raw SysEx byte. Empty slots are illegal/non-canonical values. This helper makes the
up/down buttons jump only among valid values.

Add this function near the other helper functions:

```python
def step_efx_value(param, direction):
    current = param[1]
    vals = param[2]

    if isinstance(vals, list):
        valid = [raw for raw, shown in enumerate(vals) if shown != ""]
        if not valid:
            return current

        if current not in valid:
            # Recover gracefully if an old/noncanonical value gets loaded.
            current = min(valid, key=lambda x: abs(x - current))

        pos = valid.index(current)
        return valid[(pos + direction) % len(valid)]

    # Fallback for any old-format parameter still present.
    return (current + direction) % 128
```

Then replace:

```python
if upClicked:
    efxParams[i][1]+=1
    ...
if downClicked:
    efxParams[i][1]+=-1
    ...
efxParams[i][1]=efxParams[i][1] % 128
```

with:

```python
if upClicked:
    efxParams[i][1] = step_efx_value(efxParams[i], +1)
    willSendLite = True
    changed = i
    doingStuff = True

if downClicked:
    efxParams[i][1] = step_efx_value(efxParams[i], -1)
    willSendLite = True
    changed = i
    doingStuff = True
```

Also simplify the display-list block to:

```python
if isinstance(vals, list):
    shownValue = vals[efxParams[i][1]]
    if shownValue == "":
        shownValue = "out of range!"
```

The old special cases for `-12.12`, `LCR`, and `vals[0]=='L63'` are no longer needed,
because the generator has already expanded those codecs into raw-byte-indexed display arrays.

Finally, remove this old transmission adjustment:

```python
if efxParams[i][2]=='-12.12':
    toSend+=52
```

`efxParams[i][1]` is now already the actual byte to transmit.
