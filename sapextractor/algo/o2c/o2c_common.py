from datetime import datetime

import pandas as pd

from sapextractor.utils import constants
from sapextractor.utils.dates import timestamp_column_from_dt_tm
from sapextractor.utils.vbtyp import extract_vbtyp


def vbfa_closure(vbfa):
    vbeln_unique = set(vbfa["VBELN"].unique())
    vbfa_vbelv_types = list((x["VBELV"], x["VBTYP_V"]) for x in vbfa[["VBELV", "VBTYP_V"]].to_dict("records") if
                            x["VBELV"] not in vbeln_unique)
    # default the timestamp
    closure_events = {"VBELN": [x[0] for x in vbfa_vbelv_types], "VBTYP_N": [x[1] for x in vbfa_vbelv_types],
                      "event_timestamp": datetime.fromtimestamp(10000000)}
    closure_df = pd.DataFrame(closure_events)
    return pd.concat([vbfa, closure_df]).sort_values("event_timestamp")


def apply(con, keep_first=True):
    vbfa = con.prepare_and_execute_query("VBFA", ["ERDAT", "ERZET", "VBELN", "VBELV", "VBTYP_N", "VBTYP_V"])
    timestamp_column_from_dt_tm.apply(vbfa, "ERDAT", "ERZET", "event_timestamp")
    doc_types = set(vbfa["VBTYP_N"].unique()).union(set(vbfa["VBTYP_V"].unique()))
    vbtyp = extract_vbtyp.apply_static(con, doc_types=doc_types)
    vbfa["VBTYP_N"] = vbfa["VBTYP_N"].map(vbtyp)
    vbfa["VBTYP_V"] = vbfa["VBTYP_V"].map(vbtyp)
    vbfa = vbfa_closure(vbfa)
    vbfa["event_id"] = vbfa.index.astype(str)
    cols = {}
    for x in vbfa.columns:
        if x.startswith("event_"):
            cols[x] = x
        else:
            cols[x] = "event_" + x
    vbfa = vbfa.rename(columns=cols)
    vbfa["event_activity"] = "Create " + vbfa["event_VBTYP_N"]
    if not keep_first:
        vbfa["event_activity"] = vbfa["event_activity"] + " Item"
    vbfa["INVOLVED_DOCUMENTS"] = vbfa["event_VBELV"].astype(str) + constants.DOC_SEP + vbfa["event_VBELN"].astype(str)
    vbfa["INVOLVED_DOCUMENTS"] = vbfa["INVOLVED_DOCUMENTS"].apply(constants.set_documents)
    vbfa = vbfa.reset_index()
    return vbfa
