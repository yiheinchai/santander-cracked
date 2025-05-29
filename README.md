# TfL Cycle Hire - Unofficial Python SDK & Streamlit App

This repository contains an unofficial Python SDK and a minimalistic Streamlit application for interacting with parts of the Transport for London (TfL) Cycle Hire API. This project was developed through observation of API calls and iterative experimentation.

**⚠️ DISCLAIMER:** This is an unofficial client. It relies on observed API behavior and specific example tokens that are **highly likely to be unstable, short-lived, or subject to change without notice.** This project is primarily for educational, experimental, and demonstration purposes. **Do not rely on this for critical applications.** Using unofficial clients may also be against the API provider's Terms of Service. Proceed with caution and at your own risk.

## Features

-   **Python SDK (`TflCycleHireSDK`):**
    -   Search for cycle hire docking stations by text query.
    -   Get a release code for a cycle from a specific station (either predefined static examples or stations found via search).
    -   Experimental "smart" token management:
        -   Attempts to reuse active/cached `c3-encoding` and `c3-clienttime` tokens.
        -   Can try using an active `c3-encoding` with a freshly generated `c3-clienttime`.
        -   Can prime its active tokens from a set of static example location data.
    -   Methods for explicit token control if smart strategies are insufficient or undesired.
-   **Minimalistic Streamlit App:**
    -   Search for stations by name/keyword.
    -   Select a hirable station from the search results.
    -   Request and display a bike release code for the selected station.

## Our Journey of Discovery & Experimentation

This project evolved through a series of observations and experiments:

1.  **Initial cURL Analysis:** We started with a `curl` command to get a bike release code for a specific station ("Cromer Street, Bloomsbury"). This revealed key headers (`Host`, `c3-encoding`, `User-Agent`) and data parameters (`c3-clienttime`, `Node` XML, `c3-userauth`, etc.). The `Node` parameter itself contained an XML-like structure with a `TargetUri` specifying the station.

2.  **First Python Script:** A Python script using the `requests` library was created to replicate the initial cURL. We encountered and bypassed an `SSLError: CERTIFICATE_VERIFY_FAILED` by using `verify=False`, a common step for APIs with self-signed or private CAs (with noted security implications).

3.  **Multi-Location & SDK Conception:** Additional cURL commands for different locations ("Taviton Street", "Warren Street Station") were provided. This highlighted that:

    -   `c3-encoding` and `c3-clienttime` changed for each request.
    -   Other parameters like `c3-userauth`, `c3-deviceid` seemed constant _across these examples_.
    -   The `TerminalName` and `PointName` within the `Node`'s `TargetUri` were key to specifying the location.
        This led to the creation of a basic SDK class with a `LOCATION_DATA` dictionary to store these example specifics and a method to choose a location. `typing.Literal` was used for IDE autocompletion of location keys.

4.  **Token Reusability Experiments - The Big Surprise!**

    -   **Hypothesis:** `c3-encoding`/`c3-clienttime` pairs were expected to be single-use and tightly bound to the specific request parameters (like target station).
    -   **Experiment 1 (Immediate Reusability):**
        -   An initial call for "Cromer Street" succeeded.
        -   Reusing the _exact same_ `c3-encoding` and `c3-clienttime` for "Cromer Street" again _immediately_ **also succeeded** (unexpected!).
        -   Reusing "Cromer Street's" tokens for a _different_ station ("Taviton Street") by only changing the `Node` payload **also succeeded**, returning the correct code for Taviton Street (highly unexpected!).
    -   **Experiment 2 (Short-Term Expiry & Time Manipulation):**
        -   An initial call for "Taviton Street" (using its own example tokens) succeeded.
        -   After a 2-minute delay, reusing the _same_ Taviton tokens **still succeeded** (unexpected!).
        -   After the delay, reusing Taviton's original `c3-encoding` but with a _freshly generated `c3-clienttime`_ (current timestamp) **still succeeded** (extremely unexpected!).
    -   **Experiment 3 (Simulated "Old" Tokens):** Reusing tokens that had been used multiple times over ~2.5 minutes **still succeeded**.
    -   **Conclusions from Experiments (for these specific example tokens):**
        -   The example `c3-encoding`/`c3-clienttime` pairs were **not single-use** for the "Confirm Hire" action.
        -   The example `c3-encoding` was **not strictly tied to a specific `TerminalName`/`PointName`**; the `Node` payload determined the target.
        -   The example tokens were **valid for at least several minutes** and multiple uses.
        -   The `c3_clienttime` seemed **loosely coupled** with `c3_encoding` for these successful reuses.

5.  **SDK Enhancements based on Findings:**

    -   The SDK was improved to include an internal "active token cache" (`_active_c3_encoding`, `_active_original_c3_clienttime`).
    -   "Smart" methods like `get_release_code_for_static_location()` were developed to try:
        1.  Using fully active/cached tokens.
        2.  Using active/cached `c3-encoding` with a fresh `c3-clienttime`.
        3.  Falling back to the static example tokens stored for a specific location.
    -   Methods like `set_active_tokens()` and `prime_tokens_from_static_location()` were added for better token management.

6.  **Station Search Functionality:**

    -   A new cURL for `/Clients/TfL/GenerateLCHSDynamicSearch` was introduced.
    -   The SDK was extended with a `search_stations()` method.
    -   Parser logic was developed to extract `StationID`, `Name`, `Subtitle`, `TerminalName` (crucial for hiring), and `PointName` from the search results. Some initial parsing issues with incomplete data for certain stations were addressed.
    -   The `search_stations()` method was also enhanced to use "smart token strategies" similar to the hire methods, including an option to `prime_from_static_if_no_active`.

7.  **Improved Developer Experience (DX) for Searched Stations:**

    -   A new method `get_release_code_for_searched_station(station_info: SearchedStationInfo, ...)` was added. This method takes a station object (as returned by `search_stations`) and internally uses the SDK's active token strategies to attempt to get a release code, simplifying the developer's workflow significantly.

8.  **Streamlit Application:**
    -   A minimalistic Streamlit app was created as a UI for the SDK.
    -   It allows users to search for stations.
    -   It displays hirable stations from search results.
    -   Users can select a station and click a button to get a release code, which is then displayed.
    -   The Streamlit app leverages the SDK's internal token management (priming from static data for initial actions, then using active tokens).

## Current Status & Limitations

-   **Token Dependency:** The SDK heavily relies on the initial set of example `c3-userauth`, `c3-encoding`, and `c3_clienttime` values. The observed reusability of `c3-encoding`/`c3_clienttime` is remarkable but **cannot be guaranteed to last.**
-   **"Tomorrow" Test Pending:** The true long-term validity of these tokens (especially `c3_userauth`) is unknown. A test after 12-24 hours is crucial to understand their actual lifespan.
-   **No Authentication Flow:** The SDK does not implement any login/authentication mechanism to obtain a fresh `c3_userauth` token.
-   **No `c3_encoding` Generation:** The SDK cannot generate new `c3_encoding` values from scratch. It only reuses or slightly adapts (via fresh `c3_clienttime`) the provided examples.
-   **API Stability:** As an unofficial client, any changes to the TfL API endpoints, request/response formats, or authentication mechanisms will likely break this SDK.

## Future Roadmap / Vision

The ultimate goal would be a fully autonomous SDK:

1.  **Confirm True Token Lifespan:** Execute the "Tomorrow" test.
2.  **Discover Authentication Flow:** Use network proxy tools (e.g., `mitmproxy`) to intercept the official app's login process and understand how `c3_userauth` is obtained.
3.  **Discover `c3_encoding` Generation:** Similarly, proxy the app to determine if `c3_encoding` is fetched from another endpoint or generated client-side (and if so, how).
4.  **Implement Autonomous SDK:**
    -   Add a `sdk.login(username, password)` method.
    -   Add an internal `sdk._get_fresh_c3_encoding()` method.
    -   All public methods like `get_release_code()` and `search_stations()` would then internally call these to handle all token management transparently.
        This would remove the dependency on any hardcoded example tokens.

## Setup & Usage

1.  **Prerequisites:**

    -   Python 3.8+
    -   `requests` library (`pip install requests`)
    -   `streamlit` library (`pip install streamlit`) (for the app)

2.  **SDK Code:** The Python SDK code is contained within `tfl_cycle_sdk.py` (or your chosen filename). It includes the `TflCycleHireSDK` class and related definitions.

3.  **Running the Streamlit App:**

    -   Ensure the entire SDK code is in the same file as the Streamlit app logic (or properly importable).
    -   Run: `streamlit run your_streamlit_app_file.py`

4.  **Using the SDK directly (example):**

    ```python
    from your_sdk_file import TflCycleHireSDK, DEFAULT_LOCATION_DATA, StaticallyDefinedLocationKey, SearchedStationInfo # Adjust import as needed
    import logging

    logging.basicConfig(level=logging.INFO) # To see SDK logs

    sdk = TflCycleHireSDK()

    # Example: Prime tokens and get code for a static location
    if sdk.prime_tokens_from_static_location("cromer_street"):
        try:
            code = sdk.get_release_code_for_static_location("taviton_street")
            print(f"Taviton Street Code: {code}")
        except Exception as e:
            print(f"Error: {e}")

    # Example: Search and get code for a searched station
    try:
        # For search, SDK tries active tokens, or can prime from a static one if none active
        found_stations = sdk.search_stations("Holborn", prime_from_static_if_no_active="warren_street_station")
        if found_stations:
            hirable_station = next((s for s in found_stations if s.get('terminal_name')), None)
            if hirable_station:
                print(f"Attempting code for: {hirable_station['name']}")
                code = sdk.get_release_code_for_searched_station(hirable_station)
                print(f"Code for {hirable_station['name']}: {code}")
            else:
                print("No hirable stations found in Holborn search.")
    except Exception as e:
        print(f"Error during search/hire flow: {e}")
    ```

## Contributing

Given the experimental nature and reliance on potentially unstable API observations, direct contributions for new features might be challenging until the token generation/authentication flow is better understood. However, suggestions, bug reports (especially regarding parsing or existing logic), and results from further token experiments are welcome via Issues.
If you manage to reverse-engineer the full authentication or `c3_encoding` generation, that would be a game-changing contribution!

---
