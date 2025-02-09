from flask import Flask, render_template, request, make_response, jsonify, redirect, url_for, send_file
import base64
import json
from sapextractor import factory
import tempfile
from flask_cors import CORS
from sapextractor.database_connection import factory as database_factory
import pm4py
from pm4py.objects.dfg.filtering import dfg_filtering
import uuid


app = Flask(__name__)
CORS(app, expose_headers=["x-suggested-filename"])


def __process_parameters(parameters):
    try:
        parameters = json.loads(base64.b64decode(parameters))
    except:
        import traceback
        traceback.print_exc()
        parameters = {}

    return parameters


def __get_log_type_from_ext_type(ext_type):
    if "obj_centr" in ext_type or "ocel" in ext_type:
        return 0
    elif "dataframe" in ext_type or "csv" in ext_type:
        return 1
    elif "log" in ext_type or "xes" in ext_type:
        return 2


def __prepare_event_log(parameters):
    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}
    process = parameters["process"] if "process" in parameters else "ap_ar"
    ext_type = parameters["ext_type"] if "ext_type" in parameters else "document_flow_log"
    ext_arg = parameters["ext_args"] if "ext_args" in parameters else {}

    log = factory.apply(db_type, db_con_args, process, ext_type, ext_arg)

    return log


@app.route('/')
def empty_path():
    return redirect(url_for('welcome'))


@app.route('/index.html')
def index():
    return redirect(url_for('welcome'))


@app.route("/welcome")
def welcome():
    response = make_response(render_template('extraction.html'))
    return response


@app.route('/new_extractor.html')
def new_extractor():
    response = make_response(render_template('new_extractor.html'))
    return response


@app.route("/newExtractorGetTableCount")
def getTableCount():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}
    table = parameters["table"]

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.utils.table_count import get
    return {"count": get.apply(c, table)}


@app.route("/newExtractorGetMainObjectClasses")
def getMainObjectClasses():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}
    mandt = parameters["mandt"]

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.utils.objclass_to_tables import get
    return get.apply(c, mandt)

@app.route("/newExtractorGetMainTablesPerObjectClass")
def getMainTablesPerObjectClass():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}
    mandt = parameters["mandt"]
    objectclass = parameters["objectclass"]

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.utils.objclass_to_tables import convert
    return {"obj_class_tables": list(convert.apply(c, objectclass, mandt))}

@app.route("/newExtractorGetPrimaryKeys")
def getPrimaryKeys():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}
    tabnames = parameters["tabnames"]

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.utils.preprocessing_fields import get_fields
    return {"primary_keys": get_fields.apply(c, tabnames)}

@app.route("/newExtractorGetPrimaryKeyValue")
def getPrimaryKeyValue():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}
    tabnames = parameters["tabnames"]
    fname = parameters["fname"]

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.utils.preprocessing_fields import get_field_values
    return {"values": get_field_values.apply(c, tabnames, fname)}

@app.route("/newExtractorExpandTable")
def expandTable():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}
    table = parameters["table"]

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.utils.table_expansion import expand
    return {"expanded_tables": sorted(list(expand.expand(c, table)))}


@app.route("/newExtractorExpandTables")
def expandTables():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}
    tabnames = parameters["tabnames"]

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.utils.table_expansion import expand
    from sapextractor.utils.table_fields import extract_fields
    from sapextractor.utils.dbstattora import extract_count
    dbstattora = extract_count.apply_static(c)
    tables = expand.expand_set(c, tabnames)
    tables_count = {}
    for x in tables:
        extract_fields.apply_static(c, x)
        tables_count[x] = dbstattora[x] if x in dbstattora else 1

    edges = expand.extract_expansion_graph(c, tables)

    for x in tables:
        extract_fields.apply_static(c, x)
        tables_count[x] = dbstattora[x] if x in dbstattora else 1

    ret = {"expanded_tables": sorted(list(tables)), "types": {x: extract_fields.classify_table(c, x, tables) for x in tables}, "tables_count": tables_count, "initial_tabnames": tabnames, "edges": edges}
    print(ret)
    return ret


@app.route("/newExtractorPerformExtraction")
def newExtractorPerformExtraction():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}
    tabnames = parameters["tabnames"]
    key_spec = parameters["key_spec"]
    mandt = parameters["mandt"]

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.utils.generic_extractors import extract_table
    file_name = str(uuid.uuid4())+".parquet"
    df = extract_table.apply_set_tables(c, tabnames, mandt=mandt)

    from pm4pymdl.objects.mdl.exporter import exporter
    exporter.apply(df, file_name)

    obj_types = [x for x in df.columns if not x.startswith("event_")]
    return {"file_name": file_name, "obj_types": obj_types}


@app.route("/newExtractorDownloadLog")
def newExtractorDownloadLog():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    file_name = parameters["file_name"]

    resp = send_file(file_name,
                       mimetype="text/plain",  # use appropriate type based on file
                       as_attachment=True,
                       conditional=False)
    resp.headers["x-suggested-filename"] = file_name

    return resp


@app.route("/newExtractorDownloadSvg")
def newExtractorDownloadSvg():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    file_name = parameters["file_name"]

    from pm4pymdl.objects.mdl.importer import importer as mdl_importer
    df = mdl_importer.apply(file_name)

    from pm4pymdl.algo.mvp.gen_framework3 import discovery as mvp_discovery
    model = mvp_discovery.apply(df)
    from pm4pymdl.visualization.mvp.gen_framework3 import visualizer as mvp_visualizer
    gviz = mvp_visualizer.apply(model, parameters={"format": "svg"})

    ser = pm4py.visualization.dfg.visualizer.serialize(gviz).decode("utf-8")

    return ser


@app.route("/newExtractorCheckConnection")
def checkConnection():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}

    c = database_factory.apply(db_type, db_con_args)
    return "yes"


@app.route("/o2cClientTable")
def o2cClientTable():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.algo.o2c import freq_client
    return {"res": freq_client.apply(c)}


@app.route("/aparClientTable")
def aparClientTable():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.algo.ap_ar import freq_doc_types
    return {"res": freq_doc_types.apply(c)}


@app.route("/p2pClientTable")
def p2pClientTable():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.algo.p2p import freq_doc_types
    return {"res": freq_doc_types.apply(c)}


@app.route("/vbfaGetDfg")
def vbfaGetDfg():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.algo.o2c import graph_retrieval_util
    dfg, act_count, sa, ea = graph_retrieval_util.extract_dfg(c)
    dfg, sa, ea, act_count = dfg_filtering.filter_dfg_on_paths_percentage(dfg, sa, ea, act_count, 0.2, keep_all_activities=False)
    gviz = pm4py.visualization.dfg.visualizer.apply(dfg, activities_count=act_count, parameters={"format": "svg", "start_activities": sa, "end_activities": ea})
    ser = pm4py.visualization.dfg.visualizer.serialize(gviz).decode("utf-8")
    dfg = sorted([[x[0], x[1], y] for x, y in dfg.items()], key=lambda x: x[1], reverse=True)
    act_count = sorted([(x, y) for x, y in act_count.items()], key=lambda x: x[1], reverse=True)

    return jsonify({"dfg": dfg, "act_count": act_count, "ser": ser})


@app.route("/bkpfGetDfg")
def bkpfGetDfg():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.algo.ap_ar import graph_retrieval_util
    dfg, act_count, sa, ea = graph_retrieval_util.extract_dfg_apar(c)
    dfg, sa, ea, act_count = dfg_filtering.filter_dfg_on_paths_percentage(dfg, sa, ea, act_count, 0.2, keep_all_activities=False)
    gviz = pm4py.visualization.dfg.visualizer.apply(dfg, activities_count=act_count, parameters={"format": "svg", "start_activities": sa, "end_activities": ea})
    ser = pm4py.visualization.dfg.visualizer.serialize(gviz).decode("utf-8")
    dfg = sorted([[x[0], x[1], y] for x, y in dfg.items()], key=lambda x: x[1], reverse=True)
    act_count = sorted([(x, y) for x, y in act_count.items()], key=lambda x: x[1], reverse=True)

    return jsonify({"dfg": dfg, "act_count": act_count, "ser": ser})


@app.route("/vbfaChangeActivityUtil")
def vbfaChangeActivityUtil():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    db_type = parameters["db_type"] if "db_type" in parameters else "sqlite"
    db_con_args = parameters["db_con_args"] if "db_con_args" in parameters else {"path": "sap.sqlite"}

    c = database_factory.apply(db_type, db_con_args)
    from sapextractor.algo.o2c import change_activities_util
    changes_count = change_activities_util.extract(c)

    return jsonify({"changes_count": changes_count})


@app.route("/downloadLog")
def download_event_log():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    log = __prepare_event_log(parameters)
    ext_type = parameters["ext_type"] if "ext_type" in parameters else "document_flow_log"
    log_type = __get_log_type_from_ext_type(ext_type)

    if log_type == 0:
        extension = ".jsonocel"
        temp_file = tempfile.NamedTemporaryFile(suffix=extension)
        temp_file.close()
        from pm4pymdl.objects.ocel.exporter import exporter as ocel_exporter
        ocel_exporter.apply(log, temp_file.name)
    elif log_type == 1:
        extension = ".csv"
        temp_file = tempfile.NamedTemporaryFile(suffix=extension)
        temp_file.close()
        log.to_csv(temp_file.name, index=False)
    elif log_type == 2:
        extension = ".xes"
        temp_file = tempfile.NamedTemporaryFile(suffix=extension)
        temp_file.close()
        from pm4py.objects.log.exporter.xes import exporter as xes_exporter
        xes_exporter.apply(log, temp_file.name)
    resp = send_file(temp_file.name,
                       mimetype="text/plain",  # use appropriate type based on file
                       as_attachment=True,
                       conditional=False)
    resp.headers["x-suggested-filename"] = "log" + extension

    return resp


@app.route("/getProcessSvg")
def get_process_svg():
    parameters = request.args.get("parameters")
    parameters = __process_parameters(parameters)

    log = __prepare_event_log(parameters)
    ext_type = parameters["ext_type"] if "ext_type" in parameters else "document_flow_log"
    log_type = __get_log_type_from_ext_type(ext_type)

    if log_type == 0:
        log.type = "succint"
        from pm4pymdl.algo.mvp.gen_framework import algorithm as discovery
        from pm4pymdl.visualization.mvp.gen_framework import visualizer as vis_factory
        model = discovery.apply(log, model_type_variant="model3", node_freq_variant="type31", edge_freq_variant="type11")
        gviz = vis_factory.apply(model, parameters={"format": "svg"})
    elif log_type == 1 or log_type == 2:
        import pandas as pd
        if type(log) is pd.DataFrame:
            from pm4py.objects.dfg.retrieval.pandas import get_dfg_graph
            dfg = get_dfg_graph(log)
            from pm4py.statistics.start_activities.pandas import get as pd_sa_get
            from pm4py.statistics.end_activities.pandas import get as pd_ea_get
            sa = pd_sa_get.get_start_activities(log)
            ea = pd_ea_get.get_end_activities(log)
        else:
            dfg, sa, ea = pm4py.discover_dfg(log)
        act_count = pm4py.get_attribute_values(log, "concept:name")
        dfg, sa, ea, act_count = dfg_filtering.filter_dfg_on_paths_percentage(dfg, sa, ea, act_count, 0.2,
                                                                              keep_all_activities=True)
        gviz = pm4py.visualization.dfg.visualizer.apply(dfg, activities_count=act_count,
                                                        parameters={"format": "svg", "start_activities": sa,
                                                                    "end_activities": ea})

    ser = pm4py.visualization.dfg.visualizer.serialize(gviz).decode("utf-8")

    return ser


def main():
    app.run(host='0.0.0.0')


if __name__ == "__main__":
    main()
