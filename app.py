import requests
import json
import re
import urllib3
import time
import logging
from typing import Literal, Dict, Any, Optional, Tuple, Union, Mapping, List, TypedDict


# --- SDK Specific Exceptions ---
# (Keep custom exceptions: TflCycleHireSDKError, TflCycleHireAPIError, etc. as defined before)
class TflCycleHireSDKError(Exception):
    """Base exception for TFL Cycle Hire SDK errors."""

    pass


class TflCycleHireAPIError(TflCycleHireSDKError):
    """Raised for API-level errors (e.g., HTTP 4xx, 5xx)."""

    def __init__(self, message, status_code=None, response_text=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class TflCycleHireDataError(TflCycleHireSDKError):
    """Raised when expected data is not found or malformed in the API response."""

    pass


class TflCycleHireConfigError(TflCycleHireSDKError):
    """Raised for configuration issues (e.g., invalid location key)."""

    pass


# --- Configure Logging ---
logger = logging.getLogger(__name__)


# --- Define Location Data ---
# This LocationKey is for the statically defined locations.
# Search results will be identified by their own unique IDs (e.g., StationID).
StaticallyDefinedLocationKey = Literal[
    "cromer_street", "taviton_street", "warren_street_station"
]

# This will store the static/example location data as before.
DEFAULT_LOCATION_DATA: Dict[StaticallyDefinedLocationKey, Dict[str, str]] = {
    "cromer_street": {
        "terminal_name": "300205",
        "point_name": "Cromer Street, Bloomsbury",
        "c3_encoding": "Kv6OJKA1JWRui1R+UltG2iCZBcb3+EMMfBu5aAhZNEXnA3QTJHKcKBLT+Hd097N5",
        "c3_clienttime": "1748480905.359684",
    },
    "taviton_street": {
        "terminal_name": "001009",
        "point_name": "Taviton Street, Bloomsbury",
        "c3_encoding": "hjQd5cl1SN7BOdmflRPMZwu1UnranBQaYc1W+u/ofJSmJa24Ca9fbkVYjg5SZ+Lg",
        "c3_clienttime": "1748481522.599196",
    },
    "warren_street_station": {
        "terminal_name": "001090",
        "point_name": "Warren Street Station, Euston",
        "c3_encoding": "Af1F2GlMLbIbykRF6YQQbhJQxCWXYsXyOdUx4M2KxIAvFtrFbaK3CmUhY1dwxDa0",
        "c3_clienttime": "1748481544.979739",
    },
}

# Structure for search results
SearchedStationInfo = TypedDict(
    "SearchedStationInfo",
    {
        "station_id": str,
        "name": str,
        "subtitle": str,  # Availability info
        "terminal_name": str,
        "point_name": str,  # This is often the same as 'name' but good to have distinct
        "dock_location": Optional[str],  # Lat,Lon string
    },
)


class TflCycleHireSDK:
    BASE_URL_WORKFLOWS = (
        "https://ce-a22.corethree.net/Workflows/HandleEventWithNode?format=json"
    )
    BASE_URL_CLIENTS_TFL = "https://ce-a22.corethree.net/Clients/TfL"  # For search

    DEFAULT_CONFIG = {
        "user_agent": "Core/202503171232 (iOS; iPad14,1; iPadOS 18.3.2; uk.gov.tfl.cyclehire)",
        "accept_language": "en-SG,en-GB;q=0.9,en;q=0.8",
        "c3_language": "en",
        "c3_applysensitivedatacheck": "y",
        "c3_scalefactor": "2.00",
        "c3_capabilities": "inlinevouchers,expirytags,bucketpopulation,vzero,creditcall-chipdna,card.io,camera,camera-front,camera-rear,ble-unknown,location-on-wheninuse,londonriders,londonridersphase2r1,londonridersphase3,londonridersphase4,3dsenabled,ebikesphase2,daypass",
        "c3_batterylevel": "-1.000000",
        "c3_userlat": "51.5282",
        "c3_userlong": "-0.121092",
        "c3_deviceid": "555D91A6-5B1E-49BC-9624-1989B4DA4833",
        "event_name": "Click",  # For HandleEventWithNode
        "c3_controlvals": "cHTnp0wCbVOhbs12x8sR4+2I/8CVACvEd8Zn5e3Tpas=",
    }
    DEFAULT_C3_USERAUTH = "564e7ff6ebbf80c4cafb4c7b7d3ea7bbc4435ad0|bcSxLxDWpaTC"

    NODE_XML_TEMPLATE_CONFIRM_HIRE = """<Node Type%3D"Node.FormControls.Button" ID%3D"page_button1" SortOrder%3D"25" TTL%3D"3600" AliasMode%3D"Passive">
<Name>Confirm hire<%2FName>
<TreeMode>Leaf<%2FTreeMode>
<Language><%2FLanguage>
<TargetUri>part%3A%2F%2FClients.TfL.EBikePhase2.ConfirmMemberHire%3FTerminalName%3D{terminal_name}%26amp%3BPointName%3D{point_name_encoded}%26amp%3BLCHS_Confirm%3D1%26amp%3BnbBikes%3D(null)<%2FTargetUri>
<Tags>
<Tag key%3D"Style.Cell.ForegroundColor">#FFFFFF<%2FTag>
<Tag key%3D"Style.Cell.BorderColor">#EE0000<%2FTag>
<Tag key%3D"Style.Cell.CenterVertically">1<%2FTag>
<Tag key%3D"Style.Cell.TextAlign">center<%2FTag>
<Tag key%3D"Style.Cell.BackgroundBorderRadius">5%<%2FTag>
<Tag key%3D"Style.Cell.Width">70%<%2FTag>
<Tag key%3D"Style.Cell.Margin.BackgroundColor">#FFFFFF<%2FTag>
<Tag key%3D"Style.Cell.BackgroundColor">#EE0000<%2FTag>
<Tag key%3D"Style.Cell.BorderWidth">1px<%2FTag>
<Tag key%3D"Style.Cell.HideNativeWidgets">1<%2FTag>
<Tag key%3D"Style.Cell.Margin">50 40 40 40<%2FTag>
<Tag key%3D"Style.Cell.FontSize">16px<%2FTag>
<Tag key%3D"Style.Class">button_set page_button1<%2FTag>
<Tag key%3D"Style.Cell.FontName">NJFont-Medium<%2FTag>
<%2FTags>
<%2FNode>"""

    def __init__(
        self,
        c3_userauth: str = DEFAULT_C3_USERAUTH,
        static_location_data_map: Optional[
            Mapping[StaticallyDefinedLocationKey, Dict[str, str]]
        ] = None,
        sdk_config: Optional[Dict[str, Any]] = None,
        disable_ssl_warnings: bool = True,
        session: Optional[requests.Session] = None,
    ):
        self.c3_userauth = c3_userauth
        self.config = {**self.DEFAULT_CONFIG, **(sdk_config or {})}
        self.static_location_data = dict(
            static_location_data_map or DEFAULT_LOCATION_DATA
        )

        if disable_ssl_warnings:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = self.config["user_agent"]

        self._active_c3_encoding: Optional[str] = None
        self._active_original_c3_clienttime: Optional[str] = None
        self._active_token_source_info: Optional[str] = None

        logger.info(f"SDK initialized. UserAuth (partial): {self.c3_userauth[:10]}...")

    @property
    def active_token_info(self) -> Dict[str, Optional[str]]:
        return {
            "c3_encoding": self._active_c3_encoding,
            "original_c3_clienttime": self._active_original_c3_clienttime,
            "source": self._active_token_source_info,
        }

    def prime_tokens_from_static_location(
        self, location_key: StaticallyDefinedLocationKey
    ) -> bool:
        if location_key not in self.static_location_data:
            logger.error(
                f"Cannot prime tokens: Static Location key '{location_key}' not found."
            )
            return False
        loc_details = self.static_location_data[location_key]
        if "c3_encoding" in loc_details and "c3_clienttime" in loc_details:
            self._active_c3_encoding = loc_details["c3_encoding"]
            self._active_original_c3_clienttime = loc_details["c3_clienttime"]
            self._active_token_source_info = f"static_example_for_{location_key}"
            logger.info(
                f"SDK active tokens primed from static data for '{location_key}'."
            )
            return True
        else:  # Should not happen with default data
            logger.warning(
                f"Cannot prime tokens: Missing token data for '{location_key}' in static_location_data."
            )
            return False

    def set_active_tokens(
        self,
        c3_encoding: str,
        original_c3_clienttime: str,
        source_info: str = "user_set",
    ):
        self._active_c3_encoding = c3_encoding
        self._active_original_c3_clienttime = original_c3_clienttime
        self._active_token_source_info = source_info
        logger.info(f"SDK active tokens explicitly set. Source: {source_info}.")

    def clear_active_tokens(self):
        self._active_c3_encoding = None
        self._active_original_c3_clienttime = None
        self._active_token_source_info = None
        logger.info("SDK active tokens cleared.")

    def _build_confirm_hire_node_xml(
        self, terminal_name: str, point_name_display: str
    ) -> str:
        point_name_encoded = point_name_display.replace(
            ",", "%2C"
        )  # As per previous findings
        return self.NODE_XML_TEMPLATE_CONFIRM_HIRE.format(
            terminal_name=terminal_name, point_name_encoded=point_name_encoded
        )

    def _execute_confirm_hire_api_call(
        self,
        terminal_name: str,
        point_name: str,
        c3_encoding: str,
        c3_clienttime: str,
        timeout: int,
    ) -> str:
        """Internal method for the 'confirm hire and get code' API call."""
        headers = {
            "Host": "ce-a22.corethree.net",
            "Accept": "*/*",
            "c3-encoding": c3_encoding,
            "Accept-Language": self.config["accept_language"],
        }
        node_xml = self._build_confirm_hire_node_xml(terminal_name, point_name)
        payload = {
            "c3-clienttime": c3_clienttime,
            "c3-language": self.config["c3_language"],
            "c3-applysensitivedatacheck": self.config["c3_applysensitivedatacheck"],
            "c3-scalefactor": self.config["c3_scalefactor"],
            "Node": node_xml,
            "c3-capabilities": self.config["c3_capabilities"],
            "c3-batterylevel": self.config["c3_batterylevel"],
            "c3-userlat": self.config["c3_userlat"],
            "c3-deviceid": self.config["c3_deviceid"],
            "c3-userlong": self.config["c3_userlong"],
            "Event": self.config["event_name"],
            "c3-controlvals": self.config["c3_controlvals"],
            "c3-userauth": self.c3_userauth,
        }

        logger.debug(
            f"Executing Confirm Hire API call for: {point_name} (Terminal: {terminal_name})"
        )
        response_obj = None
        try:
            response_obj = self.session.post(
                self.BASE_URL_WORKFLOWS,
                headers=headers,
                data=payload,
                verify=False,
                timeout=timeout,
            )
            response_obj.raise_for_status()
            data = response_obj.json()
        # ... (Robust error handling as in previous _execute_api_call) ...
        except requests.exceptions.HTTPError as http_err:
            raise TflCycleHireAPIError(
                str(http_err),
                getattr(http_err.response, "status_code", None),
                getattr(http_err.response, "text", None),
            ) from http_err
        except requests.exceptions.RequestException as req_err:
            raise TflCycleHireSDKError(f"Request failed: {req_err}") from req_err
        except json.JSONDecodeError as json_err:
            raise TflCycleHireAPIError(
                "Failed to decode JSON response.",
                getattr(response_obj, "status_code", None),
                getattr(response_obj, "text", None),
            ) from json_err

        release_code_found: Optional[str] = (
            None  # Logic from previous _execute_api_call
        )
        children = data.get("Children", [])
        for child in children:
            if (
                child.get("Name") == "Your cycle hire release code:"
                and "Subtitle" in child
            ):
                release_code_found = child.get("Subtitle")
                break
        if not release_code_found:
            for child in children:
                if child.get("ID", "").endswith("_unlockbar") and "Name" in child:
                    match = re.search(r"Release code (\d+)", child.get("Name", ""))
                    if match:
                        release_code_found = match.group(1)
                        break
        if release_code_found:
            return release_code_found
        else:
            raise TflCycleHireDataError(
                f"Could not find release code for {point_name}."
            )

    def get_release_code_with_explicit_tokens(
        self,
        terminal_name: str,  # Now takes terminal_name and point_name directly
        point_name: str,
        c3_encoding: str,
        c3_clienttime: str,
        timeout: int = 20,
        update_active_tokens_on_success: bool = True,
    ) -> str:
        logger.info(
            f"Attempting code retrieval for '{point_name}' (Terminal: {terminal_name}) with explicit tokens."
        )
        code = self._execute_confirm_hire_api_call(
            terminal_name, point_name, c3_encoding, c3_clienttime, timeout
        )
        if update_active_tokens_on_success:
            # We need a "source_info" that isn't tied to a static location key here if called directly.
            self.set_active_tokens(
                c3_encoding, c3_clienttime, f"explicit_call_for_{point_name}"
            )
        return code

    def get_release_code_for_static_location(
        self,
        location_key: StaticallyDefinedLocationKey,
        timeout: int = 20,
        try_active_original_time: bool = True,
        try_active_fresh_time: bool = True,
        try_static_location_tokens: bool = True,
    ) -> str:
        """Gets release code for a statically defined location using various token strategies."""
        logger.info(
            f"Smart attempt for release code at static location '{location_key}'."
        )
        last_error: Optional[Exception] = None

        if location_key not in self.static_location_data:
            raise TflCycleHireConfigError(
                f"Static location key '{location_key}' not found in SDK's static_location_data."
            )

        target_loc_details = self.static_location_data[location_key]
        target_terminal_name = target_loc_details["terminal_name"]
        target_point_name = target_loc_details["point_name"]

        # Strategy 1: Active tokens with original client time
        if (
            try_active_original_time
            and self._active_c3_encoding
            and self._active_original_c3_clienttime
        ):
            logger.info("Strategy: Trying active SDK tokens (original time).")
            try:
                code = self._execute_confirm_hire_api_call(
                    target_terminal_name,
                    target_point_name,
                    self._active_c3_encoding,
                    self._active_original_c3_clienttime,
                    timeout,
                )
                return code
            except Exception as e:
                logger.warning(f"Strategy (active original time) failed: {e}")
                last_error = e

        # Strategy 2: Active encoding with fresh client time
        if try_active_fresh_time and self._active_c3_encoding:
            fresh_client_time = f"{time.time():.6f}"
            logger.info(
                f"Strategy: Trying active SDK encoding with FRESH time ({fresh_client_time})."
            )
            try:
                code = self._execute_confirm_hire_api_call(
                    target_terminal_name,
                    target_point_name,
                    self._active_c3_encoding,
                    fresh_client_time,
                    timeout,
                )
                self.set_active_tokens(
                    self._active_c3_encoding,
                    fresh_client_time,
                    f"active_encoding_fresh_time_for_static_{location_key}",
                )
                return code
            except Exception as e:
                logger.warning(f"Strategy (active fresh time) failed: {e}")
                last_error = e

        # Strategy 3: Static/example tokens for the *target* location
        if try_static_location_tokens:
            if (
                "c3_encoding" in target_loc_details
                and "c3_clienttime" in target_loc_details
            ):
                logger.info(
                    f"Strategy: Trying static/example tokens for target static location '{location_key}'."
                )
                try:
                    code = self._execute_confirm_hire_api_call(
                        target_terminal_name,
                        target_point_name,
                        target_loc_details["c3_encoding"],
                        target_loc_details["c3_clienttime"],
                        timeout,
                    )
                    self.set_active_tokens(
                        target_loc_details["c3_encoding"],
                        target_loc_details["c3_clienttime"],
                        f"static_example_for_{location_key}",
                    )
                    return code
                except Exception as e:
                    logger.warning(f"Strategy (static location tokens) failed: {e}")
                    last_error = e
            else:
                logger.warning(
                    f"Strategy (static location tokens): Missing token data for '{location_key}'."
                )

        final_msg = f"All token strategies failed for static location '{location_key}'."
        if last_error:
            raise TflCycleHireSDKError(final_msg) from last_error
        else:
            raise TflCycleHireConfigError(
                final_msg + " No valid strategies enabled or configured."
            )

    def _execute_search_api_call(
        self, search_text: str, c3_encoding: str, c3_clienttime: str, timeout: int
    ) -> List[SearchedStationInfo]:
        """Internal method to execute the station search API call and parse results."""
        search_url = f"{self.BASE_URL_CLIENTS_TFL}/GenerateLCHSDynamicSearch"
        headers = {
            "Host": "ce-a22.corethree.net",
            "Accept": "*/*",
            "c3-encoding": c3_encoding,
            "Accept-Language": self.config["accept_language"],
        }
        payload = {
            "c3-clienttime": c3_clienttime,
            "c3-scalefactor": self.config["c3_scalefactor"],
            "c3-userlat": self.config["c3_userlat"],
            "c3-userlong": self.config["c3_userlong"],
            "c3-batterylevel": self.config["c3_batterylevel"],
            "c3-language": self.config["c3_language"],
            "c3-applysensitivedatacheck": self.config["c3_applysensitivedatacheck"],
            "c3-userauth": self.c3_userauth,
            "c3-controlvals": self.config["c3_controlvals"],
            "c3-capabilities": self.config["c3_capabilities"],
            "c3-deviceid": self.config["c3_deviceid"],
            "lchs_search_text": search_text,
            "postback": "1",
            "format": "json",
        }
        logger.debug(f"Executing Search API call for: '{search_text}'")
        logger.debug(f"  Search c3-encoding (partial): {c3_encoding[:15]}...")
        logger.debug(f"  Search c3-clienttime: {c3_clienttime}")

        response_obj = None
        try:
            response_obj = self.session.post(
                search_url, headers=headers, data=payload, verify=False, timeout=timeout
            )
            response_obj.raise_for_status()
            data = response_obj.json()
        except requests.exceptions.HTTPError as http_err:
            raise TflCycleHireAPIError(
                str(http_err),
                getattr(http_err.response, "status_code", None),
                getattr(http_err.response, "text", None),
            ) from http_err
        except (
            Exception
        ) as e:  # More specific request exceptions could be caught above this
            raise TflCycleHireSDKError(
                f"Search station API call unexpected error: {e}"
            ) from e

        # --- Parsing logic from previous search_stations method ---
        results: List[SearchedStationInfo] = []
        children = data.get("Children", [])
        station_data_aggregator: Dict[str, Dict[str, Any]] = {}
        for child in children:
            child_type = child.get("Type")
            child_id_str = child.get("ID", "")
            id_match = re.match(r"^(lchs_searchresult_(\d+))", child_id_str)
            if not id_match:
                continue
            station_id_prefix = id_match.group(1)
            parsed_station_id = id_match.group(2)
            if station_id_prefix not in station_data_aggregator:
                station_data_aggregator[station_id_prefix] = {
                    "raw_station_id_from_id": parsed_station_id
                }
            current_station_entry = station_data_aggregator[station_id_prefix]
            if child_type == "Node.Link":
                current_station_entry["name"] = child.get("Name")
                current_station_entry["subtitle"] = child.get("Subtitle")
                tags = child.get("Tags", {})
                current_station_entry["dock_location"] = tags.get("LCHS.DockLocation")
                if tags.get("LCHS.StationID"):
                    current_station_entry["station_id_from_link_tags"] = tags.get(
                        "LCHS.StationID"
                    )
            elif child_type == "Node.Media.Image" and child.get("Name") == "Hire now":
                tags = child.get("Tags", {})
                current_station_entry["terminal_name_from_image_tags"] = tags.get(
                    "Terminal"
                )
                current_station_entry["point_name_from_image_tags"] = tags.get(
                    "PointName"
                )
                if tags.get("StationID"):
                    current_station_entry["station_id_from_image_tags"] = tags.get(
                        "StationID"
                    )

        for prefix, collected_details in station_data_aggregator.items():
            station_id = (
                collected_details.get("station_id_from_image_tags")
                or collected_details.get("station_id_from_link_tags")
                or collected_details.get("raw_station_id_from_id")
            )
            name = collected_details.get("name")
            point_name = collected_details.get("point_name_from_image_tags") or name
            terminal_name = collected_details.get("terminal_name_from_image_tags")
            if station_id and name and point_name:
                results.append(
                    {
                        "station_id": station_id,
                        "name": name,
                        "subtitle": collected_details.get("subtitle", "N/A"),
                        "terminal_name": terminal_name,
                        "point_name": point_name,
                        "dock_location": collected_details.get("dock_location"),
                    }
                )  # type: ignore
            else:
                logger.warning(
                    f"Skipping search result (prefix {prefix}): missing core data: {collected_details}"
                )
        # --- End parsing logic ---
        return results

    def search_stations(
        self,
        search_text: str,
        timeout: int = 15,
        # Optional explicit tokens if user wants to override smart strategies
        c3_encoding_override: Optional[str] = None,
        c3_clienttime_override: Optional[str] = None,
        # Control smart strategies for search
        try_active_original_time: bool = True,
        try_active_fresh_time: bool = True,
        # New: allow priming from a static location if no active tokens
        prime_from_static_if_no_active: Optional[StaticallyDefinedLocationKey] = None,
    ) -> List[SearchedStationInfo]:
        """
        Searches for docking stations using smart token strategies or explicit overrides.
        THIS IS EXPERIMENTAL regarding token reuse for search.

        Args:
            search_text: The text to search for.
            timeout: Request timeout.
            c3_encoding_override: Explicitly provide c3_encoding for search.
            c3_clienttime_override: Explicitly provide c3_clienttime for search.
            try_active_original_time: Attempt with currently active SDK tokens and original time.
            try_active_fresh_time: Attempt with currently active SDK encoding and fresh time.
            prime_from_static_if_no_active: If no active SDK tokens, optionally prime them
                                            from a specified static location's data before trying.

        Returns:
            A list of SearchedStationInfo dictionaries.
        Raises:
            TflCycleHireSDKError: If all attempted strategies fail or no valid strategy provided.
        """
        logger.info(f"Smart search for stations: '{search_text}'")
        last_error: Optional[Exception] = None

        # Strategy 0: Explicit override tokens
        if c3_encoding_override and c3_clienttime_override:
            logger.info("Strategy (Search): Using EXPLICITLY provided override tokens.")
            try:
                results = self._execute_search_api_call(
                    search_text, c3_encoding_override, c3_clienttime_override, timeout
                )
                # Update active tokens if explicit override for search was successful
                self.set_active_tokens(
                    c3_encoding_override,
                    c3_clienttime_override,
                    f"explicit_override_for_search_{search_text}",
                )
                logger.info(
                    f"Search successful with explicit tokens. Found {len(results)} stations."
                )
                return results
            except Exception as e:
                logger.error(
                    f"Strategy (explicit override tokens for search) failed: {e}"
                )
                # If explicit tokens fail, we don't try other strategies for this call.
                raise TflCycleHireSDKError(
                    f"Explicit token override failed for search '{search_text}'."
                ) from e

        # Before trying active tokens, prime them if requested and none are active
        if prime_from_static_if_no_active and not self._active_c3_encoding:
            logger.info(
                f"No active SDK tokens. Priming from static location '{prime_from_static_if_no_active}' for search."
            )
            if not self.prime_tokens_from_static_location(
                prime_from_static_if_no_active
            ):
                # Priming failed, this strategy path is blocked unless active tokens somehow exist
                logger.warning(
                    f"Failed to prime tokens from '{prime_from_static_if_no_active}'. Proceeding without priming if active tokens exist."
                )

        # Strategy 1: Active SDK tokens with original client time
        if (
            try_active_original_time
            and self._active_c3_encoding
            and self._active_original_c3_clienttime
        ):
            logger.info("Strategy (Search): Trying active SDK tokens (original time).")
            try:
                results = self._execute_search_api_call(
                    search_text,
                    self._active_c3_encoding,
                    self._active_original_c3_clienttime,
                    timeout,
                )
                # Active tokens worked for search, no need to update them if they were already set.
                logger.info(
                    f"Search successful with active (original time) tokens. Found {len(results)} stations."
                )
                return results
            except Exception as e:
                logger.warning(
                    f"Strategy (active original time for search) failed: {e}"
                )
                last_error = e

        # Strategy 2: Active SDK encoding with fresh client time
        if try_active_fresh_time and self._active_c3_encoding:
            fresh_client_time = f"{time.time():.6f}"
            logger.info(
                f"Strategy (Search): Trying active SDK encoding with FRESH time ({fresh_client_time})."
            )
            try:
                results = self._execute_search_api_call(
                    search_text, self._active_c3_encoding, fresh_client_time, timeout
                )
                # If this succeeds, update active tokens.
                self.set_active_tokens(
                    self._active_c3_encoding,
                    fresh_client_time,
                    f"active_encoding_fresh_time_for_search_{search_text}",
                )
                logger.info(
                    f"Search successful with active encoding (fresh time). Found {len(results)} stations."
                )
                return results
            except Exception as e:
                logger.warning(f"Strategy (active fresh time for search) failed: {e}")
                last_error = e

        final_msg = f"All token strategies failed for search_stations with query '{search_text}'."
        if last_error:
            raise TflCycleHireSDKError(final_msg) from last_error
        else:
            raise TflCycleHireConfigError(
                final_msg
                + " No token strategies enabled or active/primeable tokens available."
            )

    def get_release_code_for_searched_station(
        self,
        station_info: SearchedStationInfo,
        timeout: int = 20,
        # Optional explicit tokens if user wants to override smart strategies
        c3_encoding_override: Optional[str] = None,
        c3_clienttime_override: Optional[str] = None,
        # Control smart strategies for this searched station
        try_active_original_time: bool = True,
        try_active_fresh_time: bool = True,
    ) -> str:
        """
        Gets a release code for a station object obtained from `search_stations()`.
        Uses the SDK's active/cached token strategies. THIS IS EXPERIMENTAL.

        Args:
            station_info: A SearchedStationInfo dictionary from `search_stations()`.
            timeout: Request timeout.
            c3_encoding_override: Explicitly provide c3_encoding to use, bypassing smart strategies.
            c3_clienttime_override: Explicitly provide c3_clienttime to use with override encoding.
            try_active_original_time: Attempt with currently active SDK tokens and their original time.
            try_active_fresh_time: Attempt with currently active SDK encoding and a fresh current time.

        Returns:
            The release code string.
        Raises:
            TflCycleHireConfigError: If station_info is invalid (e.g., no TerminalName).
            TflCycleHireSDKError: If all attempted strategies fail.
        """
        logger.info(
            f"Attempting release code for searched station: '{station_info['name']}' (ID: {station_info['station_id']})"
        )

        if not station_info.get("terminal_name"):
            msg = f"Cannot get release code for '{station_info['name']}': TerminalName is missing (station likely not hirable)."
            logger.error(msg)
            raise TflCycleHireConfigError(msg)

        target_terminal_name = station_info["terminal_name"]
        target_point_name = station_info[
            "point_name"
        ]  # Use point_name from search result
        last_error: Optional[Exception] = None

        # Strategy 0: Explicit override tokens
        if c3_encoding_override and c3_clienttime_override:
            logger.info(
                "Strategy: Using EXPLICITLY provided override tokens for searched station."
            )
            try:
                code = self._execute_confirm_hire_api_call(
                    target_terminal_name,
                    target_point_name,
                    c3_encoding_override,
                    c3_clienttime_override,
                    timeout,
                )
                # When explicit tokens are used, we might want to update active tokens
                # if the user indicates this is a "good" set of tokens.
                # For now, let get_release_code_with_explicit_tokens handle its own cache update logic if called directly.
                # This method focuses on consumption.
                # Or, we could add an `update_active_tokens_on_success` param here too.
                self.set_active_tokens(
                    c3_encoding_override,
                    c3_clienttime_override,
                    f"override_for_{station_info['name']}",
                )
                return code
            except Exception as e:
                logger.error(f"Strategy (explicit override tokens) failed: {e}")
                # If explicit tokens fail, we don't try other strategies for this call.
                raise TflCycleHireSDKError(
                    f"Explicit token override failed for {station_info['name']}."
                ) from e

        # Strategy 1: Active SDK tokens with original client time
        if (
            try_active_original_time
            and self._active_c3_encoding
            and self._active_original_c3_clienttime
        ):
            logger.info(
                "Strategy: Trying active SDK tokens (original time) for searched station."
            )
            try:
                code = self._execute_confirm_hire_api_call(
                    target_terminal_name,
                    target_point_name,
                    self._active_c3_encoding,
                    self._active_original_c3_clienttime,
                    timeout,
                )
                # Active tokens worked, no need to update them if they were already set.
                return code
            except Exception as e:
                logger.warning(
                    f"Strategy (active original time) for searched station failed: {e}"
                )
                last_error = e

        # Strategy 2: Active SDK encoding with fresh client time
        if try_active_fresh_time and self._active_c3_encoding:
            fresh_client_time = f"{time.time():.6f}"
            logger.info(
                f"Strategy: Trying active SDK encoding with FRESH time ({fresh_client_time}) for searched station."
            )
            try:
                code = self._execute_confirm_hire_api_call(
                    target_terminal_name,
                    target_point_name,
                    self._active_c3_encoding,
                    fresh_client_time,
                    timeout,
                )
                # If this succeeds, update active tokens to reflect this successful pairing for future use.
                self.set_active_tokens(
                    self._active_c3_encoding,
                    fresh_client_time,
                    f"active_encoding_fresh_time_for_searched_{station_info['name']}",
                )
                return code
            except Exception as e:
                logger.warning(
                    f"Strategy (active fresh time) for searched station failed: {e}"
                )
                last_error = e

        # No fallback to static_location_data for a searched station,
        # as it doesn't have a corresponding static entry by default.

        final_msg = f"All smart token strategies failed for searched station '{station_info['name']}'."
        if last_error:
            raise TflCycleHireSDKError(final_msg) from last_error
        else:
            # This case means no strategies were enabled or no active tokens were available
            raise TflCycleHireConfigError(
                final_msg + " No token strategies enabled or active tokens available."
            )


# --- Streamlit App Code ---
import streamlit as st
from typing import (
    TypedDict,
    List,
    Optional,
)  # Ensure these are imported for SearchedStationInfo
import os  # For file operations
import json  # For saving/loading favorites

# Ensure SearchedStationInfo is defined (it should be with the SDK code)
# If not, define it here:
# class SearchedStationInfo(TypedDict, total=False):
#     station_id: str
#     name: str
#     subtitle: str
#     terminal_name: Optional[str]
#     point_name: str
#     dock_location: Optional[str]

# --- Constants for Favorites Persistence ---
FAVORITES_FILE = "tfl_cycle_favorites.json"


# --- Helper Functions for Favorites Persistence ---
def load_favorites_from_file() -> List[SearchedStationInfo]:
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, "r") as f:
                favorites_data = json.load(f)
                # Basic validation: ensure it's a list
                if isinstance(favorites_data, list):
                    # Further validation could be added here to check structure of each item
                    return favorites_data
                else:
                    logger.warning(
                        f"Favorites file '{FAVORITES_FILE}' does not contain a list. Starting fresh."
                    )
                    return []
        except json.JSONDecodeError:
            logger.warning(
                f"Error decoding favorites file '{FAVORITES_FILE}'. Starting fresh."
            )
            return []
        except Exception as e:
            logger.error(f"Error loading favorites from file: {e}")
            return []  # Fallback to empty list on other errors
    return []


def save_favorites_to_file(favorites_list: List[SearchedStationInfo]):
    try:
        with open(FAVORITES_FILE, "w") as f:
            json.dump(favorites_list, f, indent=2)
        logger.info(f"Favorites saved to {FAVORITES_FILE}")
    except Exception as e:
        logger.error(f"Error saving favorites to file: {e}")


# --- SDK Initialization and State Management ---
def get_sdk():
    if "sdk" not in st.session_state:
        # Configure logging for the SDK and app
        logging.basicConfig(
            level=logging.INFO,  # Or logging.DEBUG for more SDK output
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        st.session_state.sdk = TflCycleHireSDK()
        if not st.session_state.sdk._active_c3_encoding:
            st.session_state.sdk.prime_tokens_from_static_location(
                "cromer_street"
            )  # Default priming
    return st.session_state.sdk


# Initialize session state variables
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "selected_station_info_for_code" not in st.session_state:
    st.session_state.selected_station_info_for_code = None
if "release_code" not in st.session_state:
    st.session_state.release_code = None
if "error_message" not in st.session_state:
    st.session_state.error_message = None
if "favorites" not in st.session_state:  # Load favorites from file on first run
    st.session_state.favorites = load_favorites_from_file()


# --- App UI ---
st.set_page_config(layout="centered", page_title="TfL Cycle Hire")
st.title("🚲 TfL Cycle Hire Code")

sdk_instance = get_sdk()  # Ensures SDK is initialized and logger is configured


# --- Helper Functions for Favorites (Interacting with State and File) ---
def add_to_favorites(station_info: SearchedStationInfo):
    if not any(
        fav["station_id"] == station_info["station_id"]
        for fav in st.session_state.favorites
    ):
        if station_info.get("terminal_name"):
            st.session_state.favorites.append(station_info)
            save_favorites_to_file(st.session_state.favorites)  # Save after adding
            st.success(f"Added '{station_info['name']}' to favorites!")
            st.session_state.error_message = None
        else:
            st.warning(
                f"Cannot add '{station_info['name']}' to favorites: Not currently hirable."
            )
    else:
        st.info(f"'{station_info['name']}' is already in favorites.")


def remove_from_favorites(station_id: str):
    # Find the name before removing for the success message
    station_name_to_remove = "Station"
    for fav in st.session_state.favorites:
        if fav["station_id"] == station_id:
            station_name_to_remove = fav["name"]
            break

    st.session_state.favorites = [
        fav for fav in st.session_state.favorites if fav["station_id"] != station_id
    ]
    save_favorites_to_file(st.session_state.favorites)  # Save after removing
    st.success(f"Removed '{station_name_to_remove}' from favorites.")
    st.session_state.error_message = None
    if (
        st.session_state.selected_station_info_for_code
        and st.session_state.selected_station_info_for_code["station_id"] == station_id
    ):
        st.session_state.release_code = None
        st.session_state.selected_station_info_for_code = None


def handle_get_code_for_favorite(fav_station_info: SearchedStationInfo):
    st.session_state.release_code = None  # Clear previous code display
    st.session_state.selected_station_info_for_code = (
        None  # Clear selected station for code display
    )
    st.session_state.error_message = None
    with st.spinner(f"Getting code for favorite: {fav_station_info['name']}..."):
        try:
            code = sdk_instance.get_release_code_for_searched_station(fav_station_info)
            st.session_state.release_code = code
            st.session_state.selected_station_info_for_code = fav_station_info
        except TflCycleHireSDKError as e:
            st.session_state.error_message = (
                f"Error getting code for favorite '{fav_station_info['name']}': {e}"
            )
        except Exception as e:
            st.session_state.error_message = f"An unexpected error occurred: {e}"


# --- 1. Favorites Section ---
if st.session_state.favorites:
    st.markdown("---")
    st.subheader("⭐ Your Favorite Stations")
    # Create a copy for iteration if removing items might cause issues, though st.rerun helps
    favorites_to_display = list(st.session_state.favorites)
    for fav_station in favorites_to_display:
        # Ensure fav_station is a dictionary and has 'station_id'
        if not isinstance(fav_station, dict) or "station_id" not in fav_station:
            logger.warning(f"Skipping invalid favorite item: {fav_station}")
            continue

        col1, col2, col3 = st.columns([0.6, 0.25, 0.15])
        with col1:
            st.write(
                f"**{fav_station.get('name', 'Unknown Station')}** ({fav_station.get('subtitle', 'N/A')})"
            )
        with col2:
            if st.button("Get Code", key=f"fav_getcode_{fav_station['station_id']}"):
                handle_get_code_for_favorite(fav_station)
        with col3:
            if st.button(
                "✖️",
                key=f"fav_remove_{fav_station['station_id']}",
                help="Remove from favorites",
            ):
                remove_from_favorites(fav_station["station_id"])
                st.rerun()  # Rerun to update the favorites list display immediately
    # st.caption("Favorites are saved locally in 'tfl_cycle_favorites.json'.") # Removed this as it's an implementation detail the user might not need
else:  # No favorites yet
    st.markdown("---")
    st.info(
        "No favorite stations yet. Search for stations and click '⭐' to add them here for quick access!"
    )


# --- 2. Search for Stations ---
# ... (Search UI and logic remains the same as before) ...
st.markdown("---")
search_query = st.text_input(
    "Search for a station (e.g., 'King's Cross', 'Soho'):", key="search_query_input"
)

if st.button("Search Stations", key="search_button"):
    st.session_state.search_results = []
    st.session_state.error_message = None

    if search_query:
        with st.spinner(f"Searching for '{search_query}'..."):
            try:
                results = sdk_instance.search_stations(
                    search_query, prime_from_static_if_no_active="cromer_street"
                )
                st.session_state.search_results = results
                if not results:
                    st.info("No stations found for your search.")
            except TflCycleHireSDKError as e:
                st.session_state.error_message = f"Search Error: {e}"
            except Exception as e:
                st.session_state.error_message = (
                    f"An unexpected error occurred during search: {e}"
                )
    else:
        st.warning("Please enter a search term.")


# --- Display Error Messages (centralized) ---
if st.session_state.error_message:
    st.error(st.session_state.error_message)
    # Clear error after displaying to prevent it from showing up on next interaction if not relevant
    st.session_state.error_message = None

# --- 3. Select Station from Search and Get Code ---
# ... (This section remains the same, including the "⭐ Add Fav" button logic) ...
if st.session_state.search_results:
    st.markdown("---")
    st.subheader("Search Results:")

    hirable_stations_from_search = [
        s for s in st.session_state.search_results if s.get("terminal_name")
    ]

    if not hirable_stations_from_search:
        st.info(
            "No stations with current bike availability (hirable) found in search results."
        )
        if st.session_state.search_results:
            st.caption("Other stations found (not currently hirable):")
            for s_non_hirable in st.session_state.search_results:
                if not s_non_hirable.get("terminal_name"):
                    st.write(
                        f"- {s_non_hirable['name']} ({s_non_hirable.get('subtitle', 'N/A')})"
                    )
    else:
        for station_info in hirable_stations_from_search:
            if not isinstance(station_info, dict) or "station_id" not in station_info:
                logger.warning(f"Skipping invalid search result item: {station_info}")
                continue
            key_prefix = f"search_{station_info['station_id']}"
            is_favorite = any(
                fav["station_id"] == station_info["station_id"]
                for fav in st.session_state.favorites
            )

            col_name, col_subtitle, col_action1, col_action2 = st.columns(
                [0.4, 0.3, 0.15, 0.15]
            )
            with col_name:
                st.write(f"**{station_info.get('name', 'Unknown')}**")
            with col_subtitle:
                st.caption(f"{station_info.get('subtitle', 'N/A')}")
            with col_action1:
                if st.button("Get Code", key=f"{key_prefix}_getcode"):
                    st.session_state.release_code = None
                    st.session_state.selected_station_info_for_code = None
                    st.session_state.error_message = None
                    with st.spinner(f"Getting code for {station_info['name']}..."):
                        try:
                            code = sdk_instance.get_release_code_for_searched_station(
                                station_info
                            )
                            st.session_state.release_code = code
                            st.session_state.selected_station_info_for_code = (
                                station_info
                            )
                        except TflCycleHireSDKError as e:
                            st.session_state.error_message = f"Error getting code: {e}"
                        except Exception as e:
                            st.session_state.error_message = (
                                f"An unexpected error occurred: {e}"
                            )
            with col_action2:
                if not is_favorite:
                    if st.button(
                        "⭐",
                        key=f"{key_prefix}_addfav",
                        help="Add to favorites",
                    ):
                        add_to_favorites(station_info)
                        st.rerun()
                else:
                    st.caption("✔️ Fav")


# --- 4. Display Release Code ---
# ... (This section remains the same) ...
if st.session_state.release_code and st.session_state.selected_station_info_for_code:
    st.markdown("---")
    station_name_for_display = st.session_state.selected_station_info_for_code["name"]
    st.subheader(f"✅ Release Code for {station_name_for_display}:")
    st.markdown(
        f"<h2 style='text-align: center; color: green;'>{st.session_state.release_code}</h2>",
        unsafe_allow_html=True,
    )
    st.info("This code is likely valid for a limited time (e.g., 10 minutes).")


st.markdown("---")
st.caption("Minimalistic TfL Cycle Hire App. Relies on experimental SDK features.")
st.caption(
    "Token reusability is NOT guaranteed long-term. Favorites are saved locally in 'tfl_cycle_favorites.json'."
)
