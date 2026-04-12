from __future__ import annotations

import json
import os


def main() -> None:
    import io

    import pandas as pd
    import streamlit as st

    from ruflex import (
        MembershipKind,
        NormalizationMode,
        Project,
        RuleBaseSpec,
        TaskType,
        VariableRole,
        VariableSpec,
        article_benchmark_plan,
        apply_model_preset_from_exported_study,
        apply_model_preset,
        apply_workspace_template,
        best_exported_study,
        attach_dataframe,
        clear_all_rule_bases,
        clear_experiment_history,
        concept_flow,
        compare_exported_studies,
        configure_deep_model,
        configure_flat_model,
        dashboard,
        default_training_config,
        experiment_history,
        explain,
        format_function_catalog,
        export_study_run_artifacts,
        gaussian_mf,
        gbell_mf,
        get_block_rule_base,
        get_decision_rule_base,
        get_variable,
        infer_variables,
        list_exported_studies,
        list_article_benchmark_runs,
        list_study_pipelines,
        list_training_presets,
        list_rule_targets,
        list_workspace_templates,
        load_article_benchmark,
        load_exported_study,
        make_rule_template,
        make_variable,
        model_preset,
        model_report,
        new_project,
        path_concept_flow,
        plot_project_training_history,
        plot_variable_memberships,
        predict,
        prepare_article_materials,
        project_report,
        rank_exported_studies,
        rule_base_catalog,
        rule_chain_flow,
        run_study_pipeline,
        load_project_from_exported_study,
        set_block_rule_base,
        clear_study_run_history,
        set_decision_rule_base,
        set_rule_base_catalog,
        set_variable,
        set_variable_catalog,
        study_pipeline,
        study_run_history,
        summary,
        training_preset,
        trapezoidal_mf,
        train,
        triangular_mf,
        run_article_benchmark,
    )

    st.set_page_config(page_title="RuFLEX Workbench", layout="wide")
    st.title("RuFLEX Workbench")
    st.caption("MATLAB-like toolbox workflow for hybrid deep fuzzy learning")

    if "project" not in st.session_state:
        st.session_state["project"] = None
    if "frame" not in st.session_state:
        st.session_state["frame"] = None
    if "target_column" not in st.session_state:
        st.session_state["target_column"] = None
    if "workspace_revision" not in st.session_state:
        st.session_state["workspace_revision"] = 0

    auto_export_dir = os.getenv("RUFLEX_AUTO_RESTORE_EXPORT_DIR")
    if auto_export_dir and st.session_state["project"] is None:
        try:
            restored_project = load_project_from_exported_study(auto_export_dir)
            st.session_state["project"] = restored_project
            if restored_project.dataset is not None:
                st.session_state["frame"] = restored_project.dataset.frame.copy()
            if restored_project.target_name is not None:
                st.session_state["target_column"] = restored_project.target_name
            st.session_state["workspace_revision"] += 1
        except Exception as exc:  # pragma: no cover - UI fallback path
            st.sidebar.warning(f"Failed to auto-restore exported study: {exc}")

    sidebar = st.sidebar
    sidebar.header("Workspace")
    uploaded = sidebar.file_uploader("Upload CSV dataset", type=["csv"])
    load_demo = sidebar.button("Load Demo Dataset")

    frame = None
    if uploaded is not None:
        frame = pd.read_csv(uploaded)
        st.session_state["frame"] = frame
        st.session_state["project"] = None
        st.session_state["workspace_revision"] += 1
    elif load_demo:
        frame = _build_demo_frame()
        st.session_state["frame"] = frame
        st.session_state["project"] = None
        st.session_state["workspace_revision"] += 1
    elif st.session_state["frame"] is not None:
        frame = st.session_state["frame"]

    article_banner_enabled = os.getenv("RUFLEX_UI_ARTICLE_BANNER") == "1"
    if article_banner_enabled and st.session_state["project"] is not None:
        project_for_banner = st.session_state["project"]
        st.subheader("Article Snapshot")
        banner_left, banner_middle, banner_right = st.columns((1, 1, 1))
        with banner_left:
            st.metric("Project", project_for_banner.name)
            st.metric("Model", project_for_banner.model_kind or "not configured")
        with banner_middle:
            st.metric("Task", project_for_banner.task_type)
            st.metric("Target", project_for_banner.target_name or "n/a")
        with banner_right:
            if project_for_banner.test_metrics:
                test_metrics = project_for_banner.test_metrics
                primary_metric = "r2" if project_for_banner.task_type == TaskType.REGRESSION.value else "accuracy"
                st.metric(primary_metric, f"{float(test_metrics.get(primary_metric, 0.0)):.4f}")
            else:
                st.metric("Test metrics", "n/a")

        banner_summary_left, banner_summary_right = st.columns((1, 1))
        with banner_summary_left:
            st.caption("Project summary")
            st.json(summary(project_for_banner))
        with banner_summary_right:
            if project_for_banner.training_summary is not None:
                st.caption("Training history")
                st.pyplot(plot_project_training_history(project_for_banner), use_container_width=True)

        if project_for_banner.model is not None and project_for_banner.dataset is not None:
            feature_frame = project_for_banner.dataset.frame.loc[:, list(project_for_banner.feature_names)].head(1)
            sample_payload = dashboard(project_for_banner, feature_frame, top_k_rules=3)[0]
            explain_left, explain_right = st.columns((1, 1))
            with explain_left:
                st.caption("Top decision rules for sample 0")
                if sample_payload.top_decision_rules:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "rule_name": item.rule_name,
                                    "rule_text": item.rule_text,
                                    "normalized_weight": item.normalized_weight,
                                    "contribution": item.contribution[0] if item.contribution else None,
                                }
                                for item in sample_payload.top_decision_rules
                            ]
                        ),
                        use_container_width=True,
                    )
                else:
                    st.info("No decision rules are available for the selected sample.")
            with explain_right:
                st.caption("Hidden concepts for sample 0")
                if sample_payload.hidden_concepts:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "stage": item.stage_name,
                                    "block": item.block_name,
                                    "concept": item.concept_name,
                                    "value": item.value,
                                }
                                for item in sample_payload.hidden_concepts
                            ]
                        ),
                        use_container_width=True,
                    )
                else:
                    st.info("Hidden concepts are not available for the selected sample.")

    toolbox_tab, data_tab, project_tab, variables_tab, rules_tab, train_tab, explain_tab = st.tabs(
        ["Toolbox", "Data", "Project", "Variables", "Rules", "Training", "Explainability"]
    )

    with toolbox_tab:
        st.subheader("Function Catalog")
        st.code(format_function_catalog(), language="text")

    if frame is None:
        with data_tab:
            st.info("Upload a CSV file or load the demo dataset to start.")
        with project_tab:
            st.info("Load a dataset first.")
        with variables_tab:
            st.info("Prepare a workspace first.")
        with rules_tab:
            st.info("Prepare a workspace first.")
        with train_tab:
            st.info("Prepare a workspace first.")
        with explain_tab:
            st.info("Train a project to inspect explainability.")
        return

    columns = tuple(frame.columns)
    default_target_index = len(columns) - 1

    with data_tab:
        st.subheader("Dataset")
        st.dataframe(frame.head(20), use_container_width=True)
        left, right = st.columns((1, 1))
        with left:
            st.metric("Rows", len(frame))
        with right:
            st.metric("Columns", len(frame.columns))
        buffer = io.StringIO()
        frame.info(buf=buffer)
        st.code(buffer.getvalue(), language="text")

        st.subheader("Prepare Workspace")
        target_column = st.selectbox("Target column", columns, index=default_target_index, key="workspace_target")
        task_type = st.selectbox(
            "Task type",
            (TaskType.REGRESSION.value, TaskType.BINARY_CLASSIFICATION.value),
            index=0,
            key="workspace_task_type",
        )
        model_kind = st.selectbox(
            "Model mode",
            ("flat_neuro_fuzzy", "deep_fuzzy_feature_learning"),
            key="workspace_model_kind",
        )
        term_count = st.slider(
            "Terms per input variable",
            min_value=2,
            max_value=5,
            value=3,
            key="workspace_term_count",
        )
        validation_fraction = st.slider(
            "Validation fraction",
            min_value=0.05,
            max_value=0.4,
            value=0.2,
            step=0.05,
            key="workspace_validation_fraction",
        )
        test_fraction = st.slider(
            "Test fraction",
            min_value=0.05,
            max_value=0.4,
            value=0.2,
            step=0.05,
            key="workspace_test_fraction",
        )

        if model_kind == "flat_neuro_fuzzy":
            concept_width = st.slider(
                "Flat concept count",
                min_value=1,
                max_value=5,
                value=2,
                key="workspace_concept_width",
            )
            block_size = None
            hidden_stage_count = None
        else:
            concept_width = st.slider(
                "Concept width per block",
                min_value=1,
                max_value=4,
                value=2,
                key="workspace_concept_width",
            )
            block_size = st.slider("Block size", min_value=1, max_value=4, value=2, key="workspace_block_size")
            hidden_stage_count = st.slider(
                "Hidden stage count",
                min_value=1,
                max_value=3,
                value=2,
                key="workspace_hidden_stage_count",
            )

        max_rules = st.slider(
            "Max rules per layer/block",
            min_value=2,
            max_value=16,
            value=4,
            key="workspace_max_rules",
        )

        st.subheader("Quick Workspace Templates")
        template_preview_project = new_project("template-preview", task_type=task_type)
        attach_dataframe(
            template_preview_project,
            frame,
            target_column=target_column,
            validation_fraction=validation_fraction,
            test_fraction=test_fraction,
        )
        workspace_templates = list_workspace_templates(template_preview_project)
        workspace_template_map = {item["label"]: item for item in workspace_templates}
        selected_workspace_template_label = st.selectbox(
            "Workspace template",
            tuple(workspace_template_map),
            key="workspace_template_name",
        )
        selected_workspace_template = workspace_template_map[selected_workspace_template_label]
        st.caption(selected_workspace_template["description"])
        st.code(json.dumps(selected_workspace_template, indent=2), language="json")

        if st.button("Prepare From Template", use_container_width=True):
            project = new_project("ruflex-workbench", task_type=task_type)
            attach_dataframe(
                project,
                frame,
                target_column=target_column,
                validation_fraction=validation_fraction,
                test_fraction=test_fraction,
            )
            apply_workspace_template(project, selected_workspace_template["name"])
            st.session_state["project"] = project
            st.session_state["target_column"] = target_column
            st.session_state["workspace_revision"] += 1
            st.success("Workspace prepared from template.")
            st.rerun()

        if st.button("Prepare Workspace", type="primary", use_container_width=True):
            project = _prepare_workspace(
                frame=frame,
                target_column=target_column,
                task_type=task_type,
                model_kind=model_kind,
                term_count=term_count,
                validation_fraction=validation_fraction,
                test_fraction=test_fraction,
                concept_width=concept_width,
                block_size=block_size,
                hidden_stage_count=hidden_stage_count,
                max_rules=max_rules,
            )
            st.session_state["project"] = project
            st.session_state["target_column"] = target_column
            st.session_state["workspace_revision"] += 1
            st.success("Workspace prepared. You can now edit variables and rules before training.")

        if st.session_state["project"] is not None:
            st.subheader("Current Workspace Summary")
            st.json(summary(st.session_state["project"]))

    project = st.session_state["project"]
    workspace_revision = st.session_state["workspace_revision"]

    with project_tab:
        st.subheader("Project Manager")
        uploaded_manifest = st.file_uploader(
            "Upload Project Manifest JSON",
            type=["json"],
            key=f"project_manifest_upload::{workspace_revision}",
        )
        manifest_editor_key = f"project_manifest_editor::{workspace_revision}"

        if project is None:
            st.info("Prepare a workspace or load a project manifest on top of the current dataset.")
            if manifest_editor_key not in st.session_state:
                st.session_state[manifest_editor_key] = json.dumps(
                    {
                        "name": "ruflex-workspace",
                        "task_type": TaskType.REGRESSION.value,
                        "description": None,
                        "dataset_config": None,
                        "variables": [],
                        "model_kind": None,
                        "model_spec": None,
                        "training_config": None,
                        "training_summary": None,
                        "preprocessing": None,
                        "test_metrics": None,
                        "dataset_source_path": None,
                        "notes": {},
                    },
                    indent=2,
                )
            st.text_area("Project Manifest JSON", key=manifest_editor_key, height=260)
            manifest_left, manifest_right = st.columns(2)
            with manifest_left:
                if st.button(
                    "Load Project From Manifest JSON",
                    use_container_width=True,
                    key=f"apply_project_manifest_json::{workspace_revision}",
                ):
                    try:
                        payload = json.loads(st.session_state[manifest_editor_key])
                        loaded_project = Project.from_manifest(payload, frame=frame)
                        st.session_state["project"] = loaded_project
                        if loaded_project.target_name is not None:
                            st.session_state["target_column"] = loaded_project.target_name
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
            with manifest_right:
                if uploaded_manifest is not None and st.button(
                    "Load Uploaded Project Manifest",
                    use_container_width=True,
                    key=f"apply_uploaded_project_manifest::{workspace_revision}",
                ):
                    try:
                        payload = json.loads(uploaded_manifest.getvalue().decode("utf-8"))
                        loaded_project = Project.from_manifest(payload, frame=frame)
                        st.session_state["project"] = loaded_project
                        if loaded_project.target_name is not None:
                            st.session_state["target_column"] = loaded_project.target_name
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
        else:
            st.json(summary(project))
            try:
                st.json(project.dataset_summary())
            except Exception:
                pass

            manifest_json = json.dumps(project.to_manifest(), indent=2)
            if manifest_editor_key not in st.session_state:
                st.session_state[manifest_editor_key] = manifest_json

            st.subheader("Project Manifest")
            st.download_button(
                "Download Project Manifest JSON",
                data=manifest_json,
                file_name=f"{project.name}_project_manifest.json",
                mime="application/json",
                use_container_width=True,
            )
            st.text_area("Project Manifest JSON", key=manifest_editor_key, height=260)
            manifest_left, manifest_right = st.columns(2)
            with manifest_left:
                if st.button(
                    "Apply Project Manifest JSON",
                    use_container_width=True,
                    key=f"apply_current_project_manifest::{workspace_revision}",
                ):
                    try:
                        payload = json.loads(st.session_state[manifest_editor_key])
                        loaded_project = Project.from_manifest(payload, frame=frame)
                        st.session_state["project"] = loaded_project
                        if loaded_project.target_name is not None:
                            st.session_state["target_column"] = loaded_project.target_name
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
            with manifest_right:
                if uploaded_manifest is not None and st.button(
                    "Apply Uploaded Project Manifest",
                    use_container_width=True,
                    key=f"apply_uploaded_project_manifest_existing::{workspace_revision}",
                ):
                    try:
                        payload = json.loads(uploaded_manifest.getvalue().decode("utf-8"))
                        loaded_project = Project.from_manifest(payload, frame=frame)
                        st.session_state["project"] = loaded_project
                        if loaded_project.target_name is not None:
                            st.session_state["target_column"] = loaded_project.target_name
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))

            st.subheader("Model Preset")
            if project.model_spec is None:
                st.info("Configure a model first to export or import a model preset.")
            else:
                preset_payload = model_preset(project)
                preset_json = json.dumps(preset_payload, indent=2)
                preset_editor_key = f"model_preset_editor::{workspace_revision}"
                if preset_editor_key not in st.session_state:
                    st.session_state[preset_editor_key] = preset_json
                uploaded_preset = st.file_uploader(
                    "Upload Model Preset JSON",
                    type=["json"],
                    key=f"model_preset_upload::{workspace_revision}",
                )
                st.download_button(
                    "Download Model Preset JSON",
                    data=preset_json,
                    file_name=f"{project.name}_model_preset.json",
                    mime="application/json",
                    use_container_width=True,
                )
                st.text_area("Model Preset JSON", key=preset_editor_key, height=240)
                preset_left, preset_right = st.columns(2)
                with preset_left:
                    if st.button(
                        "Apply Model Preset JSON",
                        use_container_width=True,
                        key=f"apply_model_preset_json::{workspace_revision}",
                    ):
                        try:
                            payload = json.loads(st.session_state[preset_editor_key])
                            apply_model_preset(project, payload)
                            st.session_state["project"] = project
                            st.session_state["workspace_revision"] += 1
                            st.rerun()
                        except Exception as exc:  # pragma: no cover - UI path
                            st.error(str(exc))
                with preset_right:
                    if uploaded_preset is not None and st.button(
                        "Apply Uploaded Model Preset",
                        use_container_width=True,
                        key=f"apply_uploaded_model_preset::{workspace_revision}",
                    ):
                        try:
                            payload = json.loads(uploaded_preset.getvalue().decode("utf-8"))
                            apply_model_preset(project, payload)
                            st.session_state["project"] = project
                            st.session_state["workspace_revision"] += 1
                            st.rerun()
                        except Exception as exc:  # pragma: no cover - UI path
                            st.error(str(exc))

            st.subheader("Experiment History")
            history = experiment_history(project)
            if history:
                st.dataframe(pd.DataFrame(history), use_container_width=True)
                if st.button(
                    "Clear Experiment History",
                    use_container_width=True,
                    key=f"clear_experiment_history::{workspace_revision}",
                ):
                    clear_experiment_history(project)
                    st.session_state["project"] = project
                    st.rerun()
            else:
                st.info("No experiment history yet. Train the project to create records.")

            st.subheader("Study Pipelines")
            study_pipelines = list_study_pipelines(project)
            study_pipeline_map = {item["label"]: item for item in study_pipelines}
            selected_study_pipeline_label = st.selectbox(
                "Study pipeline",
                tuple(study_pipeline_map),
                key=f"project_study_pipeline::{workspace_revision}",
            )
            selected_study_pipeline = study_pipeline_map[selected_study_pipeline_label]
            st.caption(selected_study_pipeline["description"])
            st.code(json.dumps(selected_study_pipeline, indent=2), language="json")

            study_history = study_run_history(project)
            if study_history:
                st.subheader("Study Run History")
                st.dataframe(pd.DataFrame(study_history), use_container_width=True)
                latest_study_run = study_history[-1]
                st.download_button(
                    "Download Latest Study Run JSON",
                    data=json.dumps(latest_study_run, indent=2),
                    file_name=f"{project.name}_latest_study_run.json",
                    mime="application/json",
                    use_container_width=True,
                )
                artifact_export_options = {
                    f"#{index + 1} {item.get('pipeline_name', 'study_run')} @ {item.get('timestamp_utc', 'unknown')}": index
                    for index, item in enumerate(study_history)
                }
                artifact_export_root = st.text_input(
                    "Artifact export root",
                    value="experiments",
                    key=f"study_artifact_root::{workspace_revision}",
                )
                selected_artifact_export_label = st.selectbox(
                    "Study run to export",
                    tuple(artifact_export_options),
                    index=len(artifact_export_options) - 1,
                    key=f"study_artifact_run::{workspace_revision}",
                )
                if st.button(
                    "Export Study Run Artifacts",
                    use_container_width=True,
                    key=f"export_study_artifacts::{workspace_revision}",
                ):
                    try:
                        export_payload = export_study_run_artifacts(
                            project,
                            artifact_export_root,
                            study_run_index=artifact_export_options[selected_artifact_export_label],
                        )
                        st.success(f"Artifacts exported to {export_payload['export_dir']}")
                        st.json(export_payload)
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
                if st.button(
                    "Clear Study Run History",
                    use_container_width=True,
                    key=f"clear_study_run_history::{workspace_revision}",
                ):
                    clear_study_run_history(project)
                    st.session_state["project"] = project
                    st.rerun()
            else:
                st.info("No study pipelines have been executed yet.")

            st.subheader("Experiment Browser")
            browser_root = st.text_input(
                "Experiment root",
                value="experiments",
                key=f"experiment_browser_root::{workspace_revision}",
            )
            exported_studies = list_exported_studies(project, browser_root)
            if exported_studies:
                comparison_rows = compare_exported_studies(project, browser_root)
                st.dataframe(pd.DataFrame(comparison_rows), use_container_width=True)
                metric_names = _exported_metric_names(exported_studies)
                if metric_names:
                    ranking_left, ranking_mid = st.columns(2)
                    with ranking_left:
                        selected_ranking_metric = st.selectbox(
                            "Ranking metric",
                            tuple(metric_names),
                            key=f"experiment_browser_metric::{workspace_revision}",
                        )
                    with ranking_mid:
                        ranking_goal = st.selectbox(
                            "Ranking goal",
                            ("auto", "maximize", "minimize"),
                            index=0,
                            key=f"experiment_browser_goal::{workspace_revision}",
                        )
                    higher_is_better = None
                    if ranking_goal == "maximize":
                        higher_is_better = True
                    elif ranking_goal == "minimize":
                        higher_is_better = False

                    ranked_rows = rank_exported_studies(
                        project,
                        browser_root,
                        metric_name=selected_ranking_metric,
                        higher_is_better=higher_is_better,
                    )
                    ranking_table = [
                        {
                            "rank": row["rank"],
                            "directory_name": row["directory_name"],
                            "pipeline_name": row["pipeline_name"],
                            "ranking_split": row["ranking_split"],
                            "ranking_value": row["ranking_value"],
                            "timestamp_utc": row["timestamp_utc"],
                            "model_kind": row["model_kind"],
                            "export_dir": row["export_dir"],
                        }
                        for row in ranked_rows
                    ]
                    st.subheader("Metric Ranking")
                    st.dataframe(pd.DataFrame(ranking_table), use_container_width=True)

                    try:
                        best_run = best_exported_study(
                            project,
                            browser_root,
                            metric_name=selected_ranking_metric,
                            higher_is_better=higher_is_better,
                        )
                        st.success(
                            "Best run: "
                            f"{best_run['directory_name']} | {best_run['ranking_split']} {best_run['ranking_metric']}="
                            f"{best_run['ranking_value']:.6f}"
                        )
                        if st.button(
                            "Apply Best Model Preset",
                            use_container_width=True,
                            key=f"apply_best_exported_model_preset::{workspace_revision}",
                        ):
                            try:
                                apply_model_preset_from_exported_study(project, best_run["export_dir"])
                                st.session_state["project"] = project
                                st.session_state["workspace_revision"] += 1
                                st.rerun()
                            except Exception as exc:  # pragma: no cover - UI path
                                st.error(str(exc))
                    except Exception as exc:  # pragma: no cover - UI path
                        st.warning(str(exc))

                study_option_map = {
                    f"{item['directory_name']} | {item.get('pipeline_name', 'unknown')} | {item.get('timestamp_utc', 'unknown')}": item[
                        "export_dir"
                    ]
                    for item in exported_studies
                }
                selected_export_label = st.selectbox(
                    "Exported study",
                    tuple(study_option_map),
                    key=f"experiment_browser_selection::{workspace_revision}",
                )
                if st.button(
                    "Apply Selected Model Preset",
                    use_container_width=True,
                    key=f"apply_selected_exported_model_preset::{workspace_revision}",
                ):
                    try:
                        apply_model_preset_from_exported_study(project, study_option_map[selected_export_label])
                        st.session_state["project"] = project
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
                if st.button(
                    "Restore Project From Exported Study",
                    use_container_width=True,
                    key=f"restore_project_from_exported_study::{workspace_revision}",
                ):
                    try:
                        restored_project = load_project_from_exported_study(
                            study_option_map[selected_export_label],
                            frame=frame,
                        )
                        st.session_state["project"] = restored_project
                        if restored_project.target_name is not None:
                            st.session_state["target_column"] = restored_project.target_name
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
                loaded_export = load_exported_study(project, study_option_map[selected_export_label])
                st.caption(f"Available files: {', '.join(loaded_export['available_files'])}")
                if loaded_export["project_summary"] is not None:
                    st.json(loaded_export["project_summary"])
                if loaded_export["metrics"] is not None:
                    st.json(loaded_export["metrics"])
                if loaded_export["study_pipeline"] is not None:
                    st.code(json.dumps(loaded_export["study_pipeline"], indent=2), language="json")
                if loaded_export["project_report"] is not None:
                    st.code(loaded_export["project_report"], language="text")
                if loaded_export["model_report"] is not None:
                    st.code(loaded_export["model_report"], language="text")
            else:
                st.info("No exported study artifacts were found under the selected experiment root.")

            st.subheader("Article Materials")
            article_benchmark_root = st.text_input(
                "Article benchmark root",
                value="experiments/article_benchmark",
                key=f"article_materials_benchmark_root::{workspace_revision}",
            )
            article_assets_root = st.text_input(
                "Article assets root",
                value="docs/article/assets",
                key=f"article_materials_assets_root::{workspace_revision}",
            )
            benchmark_runs = list_article_benchmark_runs(article_benchmark_root)
            if benchmark_runs:
                st.dataframe(pd.DataFrame(benchmark_runs), use_container_width=True)
                benchmark_run_map = {
                    f"{item['directory_name']} | {item.get('source_project_name', 'unknown')} | {item.get('generated_at_utc', 'unknown')}": item[
                        "benchmark_dir"
                    ]
                    for item in benchmark_runs
                }
                selected_benchmark_run_label = st.selectbox(
                    "Saved benchmark run",
                    tuple(benchmark_run_map),
                    key=f"article_materials_selected_benchmark::{workspace_revision}",
                )
                loaded_benchmark = load_article_benchmark(benchmark_run_map[selected_benchmark_run_label])
                st.json(
                    {
                        "benchmark_dir": loaded_benchmark["benchmark_dir"],
                        "source_project": loaded_benchmark["source_project"],
                        "variant_count": len(loaded_benchmark["results"]),
                    }
                )
                benchmark_results = list(loaded_benchmark["results"])
                st.dataframe(pd.DataFrame(benchmark_results), use_container_width=True)
                benchmark_metric_names = _benchmark_result_metric_names(benchmark_results)
                if benchmark_metric_names:
                    benchmark_metric = st.selectbox(
                        "Best benchmark metric",
                        tuple(benchmark_metric_names),
                        key=f"article_benchmark_best_metric::{workspace_revision}",
                    )
                    benchmark_goal = st.selectbox(
                        "Best benchmark goal",
                        ("auto", "maximize", "minimize"),
                        index=0,
                        key=f"article_benchmark_best_goal::{workspace_revision}",
                    )
                    higher_is_better = _benchmark_metric_higher_is_better(benchmark_metric, benchmark_goal)
                    available_benchmark_rows = [row for row in benchmark_results if row.get(benchmark_metric) is not None]
                    if available_benchmark_rows:
                        best_benchmark_row = sorted(
                            available_benchmark_rows,
                            key=lambda row: float(row[benchmark_metric]),
                            reverse=higher_is_better,
                        )[0]
                        st.success(
                            "Best benchmark variant: "
                            f"{best_benchmark_row['variant_label']} | {benchmark_metric}={float(best_benchmark_row[benchmark_metric]):.6f}"
                        )
                        if st.button(
                            "Apply Best Benchmark Preset",
                            use_container_width=True,
                            key=f"apply_best_benchmark_preset::{workspace_revision}",
                        ):
                            try:
                                apply_model_preset_from_exported_study(project, best_benchmark_row["export_dir"])
                                st.session_state["project"] = project
                                st.session_state["workspace_revision"] += 1
                                st.rerun()
                            except Exception as exc:  # pragma: no cover - UI path
                                st.error(str(exc))
                        if st.button(
                            "Restore Best Benchmark Run",
                            use_container_width=True,
                            key=f"restore_best_benchmark_run::{workspace_revision}",
                        ):
                            try:
                                restored_project = load_project_from_exported_study(
                                    best_benchmark_row["export_dir"],
                                    frame=frame,
                                )
                                st.session_state["project"] = restored_project
                                if restored_project.target_name is not None:
                                    st.session_state["target_column"] = restored_project.target_name
                                st.session_state["workspace_revision"] += 1
                                st.rerun()
                            except Exception as exc:  # pragma: no cover - UI path
                                st.error(str(exc))
                    else:
                        st.info("The selected benchmark metric is not available in the saved benchmark results.")
                if st.button(
                    "Prepare Article Materials",
                    use_container_width=True,
                    key=f"prepare_article_materials::{workspace_revision}",
                ):
                    try:
                        materials_payload = prepare_article_materials(
                            benchmark_run_map[selected_benchmark_run_label],
                            output_root=article_assets_root,
                        )
                        st.success(f"Article materials prepared: {materials_payload['output_dir']}")
                        st.json(materials_payload)
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
            else:
                st.info("No saved article benchmark runs were found under the selected benchmark root.")

    with variables_tab:
        st.subheader("Variable Editor")
        if project is None or not project.variables:
            st.info("Prepare a workspace in the Data tab first.")
        else:
            variable_name = st.selectbox(
                "Variable",
                tuple(variable.name for variable in project.variables),
                key="variable_editor_name",
            )
            selected = get_variable(project, variable_name)
            editor_key = f"variable_editor::{workspace_revision}::{variable_name}"
            if editor_key not in st.session_state:
                st.session_state[editor_key] = json.dumps(selected.to_dict(), indent=2)

            st.subheader("Structured Variable Editor")
            meta_left, meta_mid, meta_right = st.columns(3)
            with meta_left:
                structured_role = st.selectbox(
                    "Role",
                    options=tuple(role.value for role in VariableRole),
                    index=tuple(role.value for role in VariableRole).index(selected.role.value),
                    key=f"variable_role::{workspace_revision}::{variable_name}",
                )
                structured_normalization = st.selectbox(
                    "Normalization",
                    options=tuple(mode.value for mode in NormalizationMode),
                    index=tuple(mode.value for mode in NormalizationMode).index(selected.normalization.value),
                    key=f"variable_norm::{workspace_revision}::{variable_name}",
                )
            with meta_mid:
                structured_data_type = st.text_input(
                    "Data type",
                    value=selected.data_type,
                    key=f"variable_dtype::{workspace_revision}::{variable_name}",
                )
                structured_kind = st.selectbox(
                    "Membership kind",
                    options=tuple(kind.value for kind in MembershipKind),
                    index=tuple(kind.value for kind in MembershipKind).index(selected.membership.kind.value),
                    key=f"variable_kind::{workspace_revision}::{variable_name}",
                )
            with meta_right:
                current_range = selected.value_range or (0.0, 1.0)
                range_min = st.number_input(
                    "Range min",
                    value=float(current_range[0]),
                    format="%.6f",
                    key=f"variable_range_min::{workspace_revision}::{variable_name}",
                )
                range_max = st.number_input(
                    "Range max",
                    value=float(current_range[1]),
                    format="%.6f",
                    key=f"variable_range_max::{workspace_revision}::{variable_name}",
                )

            st.caption("Edit membership terms in table form. Each row describes one linguistic term.")
            membership_rows = st.data_editor(
                _membership_editor_frame(selected, membership_kind=structured_kind),
                num_rows="dynamic",
                use_container_width=True,
                key=f"variable_terms::{workspace_revision}::{variable_name}",
            )
            if st.button(
                "Apply Structured Variable",
                use_container_width=True,
                key=f"apply_structured_variable::{workspace_revision}::{variable_name}",
            ):
                try:
                    variable_spec = _variable_from_editor(
                        variable_name=variable_name,
                        membership_kind=structured_kind,
                        rows=membership_rows,
                        value_range=(range_min, range_max),
                        data_type=structured_data_type,
                        role=structured_role,
                        normalization=structured_normalization,
                        gaussian_mf=gaussian_mf,
                        gbell_mf=gbell_mf,
                        triangular_mf=triangular_mf,
                        trapezoidal_mf=trapezoidal_mf,
                        make_variable=make_variable,
                    )
                    set_variable(project, variable_name, variable_spec)
                    st.session_state["project"] = project
                    st.session_state["workspace_revision"] += 1
                    st.rerun()
                except Exception as exc:  # pragma: no cover - UI path
                    st.error(str(exc))

            st.subheader("JSON Variable Editor")
            st.json(selected.to_dict())
            if selected.value_range is not None:
                st.pyplot(plot_variable_memberships(project, variable_name))
            st.text_area("Variable JSON", key=editor_key, height=320)

            apply_col, reset_col = st.columns(2)
            with apply_col:
                if st.button("Apply Variable JSON", use_container_width=True, key=f"apply_variable::{variable_name}"):
                    try:
                        payload = json.loads(st.session_state[editor_key])
                        variable_spec = VariableSpec.from_dict(payload)
                        set_variable(project, variable_name, variable_spec)
                        st.session_state["project"] = project
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
            with reset_col:
                if st.button("Reset Variable Editor", use_container_width=True, key=f"reset_variable::{variable_name}"):
                    st.session_state[editor_key] = json.dumps(get_variable(project, variable_name).to_dict(), indent=2)
                    st.rerun()

            st.subheader("Variable Catalog")
            st.json(project.variable_catalog())
            variable_catalog_json = json.dumps(project.variable_catalog(), indent=2)
            st.download_button(
                "Download Variable Catalog JSON",
                data=variable_catalog_json,
                file_name=f"{project.name}_variables.json",
                mime="application/json",
                use_container_width=True,
            )
            uploaded_variable_catalog = st.file_uploader(
                "Upload Variable Catalog JSON",
                type=["json"],
                key=f"upload_variable_catalog::{workspace_revision}",
            )
            variable_catalog_editor_key = f"variable_catalog_editor::{workspace_revision}"
            if variable_catalog_editor_key not in st.session_state:
                st.session_state[variable_catalog_editor_key] = variable_catalog_json
            st.text_area(
                "Variable Catalog JSON",
                key=variable_catalog_editor_key,
                height=220,
            )
            import_left, import_mid = st.columns(2)
            with import_left:
                if st.button(
                    "Apply Variable Catalog JSON",
                    use_container_width=True,
                    key=f"apply_variable_catalog::{workspace_revision}",
                ):
                    try:
                        payload = json.loads(st.session_state[variable_catalog_editor_key])
                        set_variable_catalog(project, payload)
                        st.session_state["project"] = project
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
            with import_mid:
                if uploaded_variable_catalog is not None and st.button(
                    "Apply Uploaded Variable Catalog",
                    use_container_width=True,
                    key=f"apply_uploaded_variable_catalog::{workspace_revision}",
                ):
                    try:
                        payload = json.loads(uploaded_variable_catalog.getvalue().decode("utf-8"))
                        set_variable_catalog(project, payload)
                        st.session_state["project"] = project
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
            if project.model is None:
                st.info("After variable changes the trained model is invalidated until you train again.")

    with rules_tab:
        st.subheader("Rule Editor")
        if project is None or project.model_spec is None:
            st.info("Prepare a workspace in the Data tab first.")
        else:
            targets = list_rule_targets(project)
            option_map = {_format_rule_target(target): target for target in targets}
            selected_label = st.selectbox("Rule target", tuple(option_map), key="rule_target_name")
            target = option_map[selected_label]
            current_rule_base = _current_rule_base(
                project,
                target=target,
                get_block_rule_base=get_block_rule_base,
                get_decision_rule_base=get_decision_rule_base,
            )
            template = make_rule_template(
                project,
                block_name=target["block_name"],
                stage_name=target["stage_name"],
                layer_kind=target["layer_kind"],
            )
            editor_key = f"rule_editor::{workspace_revision}::{_rule_target_key(target)}"
            if editor_key not in st.session_state:
                payload = template if current_rule_base is None else current_rule_base
                st.session_state[editor_key] = json.dumps(payload.to_dict(), indent=2)

            guided_source = current_rule_base or template
            default_rule_count = max(1, len(guided_source.rules))
            max_rule_count = int(target.get("max_rules") or max(default_rule_count, 8))

            st.subheader("Guided Rule Builder")
            guided_rule_count = st.number_input(
                "Rule count",
                min_value=1,
                max_value=max(1, max_rule_count),
                value=min(default_rule_count, max(1, max_rule_count)),
                step=1,
                key=f"guided_rule_count::{workspace_revision}::{_rule_target_key(target)}",
            )
            guided_rules_payload = []
            for rule_index in range(int(guided_rule_count)):
                existing_rule = guided_source.rules[rule_index] if rule_index < len(guided_source.rules) else None
                guided_rule_payload = _guided_rule_builder_section(
                    st=st,
                    target=target,
                    rule_index=rule_index,
                    workspace_revision=workspace_revision,
                    existing_rule=existing_rule,
                )
                guided_rules_payload.append(guided_rule_payload)

            if st.button(
                "Apply Guided Rule Builder",
                use_container_width=True,
                key=f"apply_guided_rule_builder::{workspace_revision}::{_rule_target_key(target)}",
            ):
                try:
                    rule_base = RuleBaseSpec.from_dict({"rules": guided_rules_payload})
                    _assign_rule_base(
                        project,
                        target=target,
                        rule_base=rule_base,
                        set_block_rule_base=set_block_rule_base,
                        set_decision_rule_base=set_decision_rule_base,
                    )
                    st.session_state["project"] = project
                    st.session_state["workspace_revision"] += 1
                    st.rerun()
                except Exception as exc:  # pragma: no cover - UI path
                    st.error(str(exc))

            st.subheader("Structured Rule Table")
            st.caption(
                "Antecedents use `variable=term` joined by `&`. Consequents use `key=value` joined by `;`."
            )
            rule_rows = st.data_editor(
                _rule_base_editor_frame(current_rule_base or template),
                num_rows="dynamic",
                use_container_width=True,
                key=f"rule_table::{workspace_revision}::{_rule_target_key(target)}",
            )
            if st.button(
                "Apply Structured Rule Table",
                use_container_width=True,
                key=f"apply_structured_rule_table::{workspace_revision}::{_rule_target_key(target)}",
            ):
                try:
                    rule_base = _rule_base_from_editor_rows(rule_rows, default_layer_name=str(target["block_name"]))
                    _assign_rule_base(
                        project,
                        target=target,
                        rule_base=rule_base,
                        set_block_rule_base=set_block_rule_base,
                        set_decision_rule_base=set_decision_rule_base,
                    )
                    st.session_state["project"] = project
                    st.session_state["workspace_revision"] += 1
                    st.rerun()
                except Exception as exc:  # pragma: no cover - UI path
                    st.error(str(exc))

            st.subheader("JSON Rule Editor")
            st.json(target)
            st.text_area("Rule Base JSON", key=editor_key, height=360)

            apply_col, template_col, clear_col = st.columns(3)
            with apply_col:
                if st.button("Apply Rule Base JSON", use_container_width=True, key=f"apply_rule_base::{editor_key}"):
                    try:
                        payload = json.loads(st.session_state[editor_key])
                        rule_base = RuleBaseSpec.from_dict(payload)
                        _assign_rule_base(
                            project,
                            target=target,
                            rule_base=rule_base,
                            set_block_rule_base=set_block_rule_base,
                            set_decision_rule_base=set_decision_rule_base,
                        )
                        st.session_state["project"] = project
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
            with template_col:
                if st.button("Load Starter Template", use_container_width=True, key=f"load_rule_template::{editor_key}"):
                    st.session_state[editor_key] = json.dumps(template.to_dict(), indent=2)
                    st.rerun()
            with clear_col:
                if st.button("Clear Selected Rule Base", use_container_width=True, key=f"clear_rule_base::{editor_key}"):
                    try:
                        _assign_rule_base(
                            project,
                            target=target,
                            rule_base=None,
                            set_block_rule_base=set_block_rule_base,
                            set_decision_rule_base=set_decision_rule_base,
                        )
                        st.session_state["project"] = project
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))

            if st.button("Clear All Rule Bases", use_container_width=True):
                clear_all_rule_bases(project)
                st.session_state["project"] = project
                st.session_state["workspace_revision"] += 1
                st.rerun()

            st.subheader("Rule Base Catalog")
            st.json(rule_base_catalog(project))
            rule_catalog_json = json.dumps(rule_base_catalog(project), indent=2)
            st.download_button(
                "Download Rule-Base Catalog JSON",
                data=rule_catalog_json,
                file_name=f"{project.name}_rule_bases.json",
                mime="application/json",
                use_container_width=True,
            )
            uploaded_rule_catalog = st.file_uploader(
                "Upload Rule-Base Catalog JSON",
                type=["json"],
                key=f"upload_rule_catalog::{workspace_revision}",
            )
            rule_catalog_editor_key = f"rule_catalog_editor::{workspace_revision}"
            if rule_catalog_editor_key not in st.session_state:
                st.session_state[rule_catalog_editor_key] = rule_catalog_json
            clear_missing = st.checkbox(
                "Clear missing targets on import",
                value=False,
                key=f"clear_missing_rule_catalog::{workspace_revision}",
            )
            st.text_area(
                "Rule-Base Catalog JSON",
                key=rule_catalog_editor_key,
                height=220,
            )
            catalog_left, catalog_mid = st.columns(2)
            with catalog_left:
                if st.button(
                    "Apply Rule-Base Catalog JSON",
                    use_container_width=True,
                    key=f"apply_rule_catalog::{workspace_revision}",
                ):
                    try:
                        payload = json.loads(st.session_state[rule_catalog_editor_key])
                        set_rule_base_catalog(project, payload, clear_missing=clear_missing)
                        st.session_state["project"] = project
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
            with catalog_mid:
                if uploaded_rule_catalog is not None and st.button(
                    "Apply Uploaded Rule-Base Catalog",
                    use_container_width=True,
                    key=f"apply_uploaded_rule_catalog::{workspace_revision}",
                ):
                    try:
                        payload = json.loads(uploaded_rule_catalog.getvalue().decode("utf-8"))
                        set_rule_base_catalog(project, payload, clear_missing=clear_missing)
                        st.session_state["project"] = project
                        st.session_state["workspace_revision"] += 1
                        st.rerun()
                    except Exception as exc:  # pragma: no cover - UI path
                        st.error(str(exc))
            if project.model is None:
                st.info("After rule-base changes the trained model is invalidated until you train again.")

    with train_tab:
        st.subheader("Train Workspace")
        if project is None or project.model_spec is None:
            st.info("Prepare a workspace first.")
        else:
            project_snapshot = summary(project)
            st.json(project_snapshot)
            manual_rule_targets = int(project_snapshot["manual_rule_targets"])
            if manual_rule_targets > 0:
                st.info(
                    "Manual rule bases are active. Refinement cycles are limited to 1 in the current RuFLEX layer."
                )

            st.subheader("Study Pipelines")
            study_pipeline_options = list_study_pipelines(project)
            study_pipeline_map = {item["label"]: item for item in study_pipeline_options}
            selected_study_pipeline_label = st.selectbox(
                "Run study pipeline",
                tuple(study_pipeline_map),
                key=f"training_study_pipeline_name::{workspace_revision}",
            )
            selected_study_pipeline = study_pipeline_map[selected_study_pipeline_label]
            st.caption(selected_study_pipeline["description"])
            st.code(json.dumps(study_pipeline(project, selected_study_pipeline["name"]), indent=2), language="json")
            auto_export_study_pipeline = st.checkbox(
                "Auto-export study artifacts after run",
                value=False,
                key=f"training_study_pipeline_auto_export::{workspace_revision}",
            )
            auto_export_root = st.text_input(
                "Auto-export root",
                value="experiments",
                key=f"training_study_pipeline_export_root::{workspace_revision}",
                disabled=not auto_export_study_pipeline,
            )
            if st.button(
                "Run Study Pipeline",
                use_container_width=True,
                key=f"run_study_pipeline::{workspace_revision}",
            ):
                try:
                    pipeline_record = run_study_pipeline(
                        project,
                        selected_study_pipeline["name"],
                        export_root=auto_export_root if auto_export_study_pipeline else None,
                    )
                    st.session_state["project"] = project
                    st.success("Study pipeline finished.")
                    st.json(pipeline_record)
                except Exception as exc:  # pragma: no cover - UI path
                    st.error(str(exc))

            st.subheader("Article Benchmark")
            benchmark_plan_payload = article_benchmark_plan(project)
            st.code(json.dumps(benchmark_plan_payload, indent=2), language="json")
            benchmark_label_map = {
                f"{item['label']} | {item['study_pipeline']}": item["name"] for item in benchmark_plan_payload
            }
            selected_benchmark_labels = st.multiselect(
                "Benchmark variants",
                options=tuple(benchmark_label_map),
                default=tuple(benchmark_label_map),
                key=f"article_benchmark_variants::{workspace_revision}",
            )
            article_benchmark_root = st.text_input(
                "Article benchmark root",
                value="experiments/article_benchmark",
                key=f"article_benchmark_root::{workspace_revision}",
            )
            benchmark_override_options = ("default_pipeline_presets",) + tuple(
                item["name"] for item in list_training_presets(project)
            )
            selected_benchmark_override = st.selectbox(
                "Training preset override",
                benchmark_override_options,
                index=0,
                key=f"article_benchmark_training_override::{workspace_revision}",
            )
            if st.button(
                "Run Article Benchmark",
                use_container_width=True,
                key=f"run_article_benchmark::{workspace_revision}",
            ):
                try:
                    benchmark_summary = run_article_benchmark(
                        project,
                        output_root=article_benchmark_root,
                        variant_names=[benchmark_label_map[label] for label in selected_benchmark_labels],
                        training_preset_override=(
                            None
                            if selected_benchmark_override == "default_pipeline_presets"
                            else selected_benchmark_override
                        ),
                    )
                    st.success(f"Article benchmark finished: {benchmark_summary['benchmark_dir']}")
                    st.dataframe(pd.DataFrame(benchmark_summary["results"]), use_container_width=True)
                    st.json(
                        {
                            "benchmark_dir": benchmark_summary["benchmark_dir"],
                            "runs_root": benchmark_summary["runs_root"],
                            "variant_count": len(benchmark_summary["results"]),
                        }
                    )
                except Exception as exc:  # pragma: no cover - UI path
                    st.error(str(exc))

            st.subheader("Training Presets")
            preset_options = list_training_presets(project)
            preset_map = {item["label"]: item for item in preset_options}
            selected_training_preset_label = st.selectbox(
                "Training preset",
                tuple(preset_map),
                key=f"training_preset_name::{workspace_revision}",
            )
            selected_training_preset = preset_map[selected_training_preset_label]
            st.caption(selected_training_preset["description"])
            st.code(json.dumps(selected_training_preset, indent=2), language="json")
            if st.button(
                "Train With Preset",
                use_container_width=True,
                key=f"train_with_preset::{workspace_revision}",
            ):
                try:
                    preset_config = training_preset(project, selected_training_preset["name"])
                    training_summary = train(project, training_config=preset_config)
                    st.session_state["project"] = project
                    st.success("Preset training finished.")
                    st.write("Training source", training_summary.source)
                    st.write("Train metrics", training_summary.train_metrics)
                    if training_summary.validation_metrics is not None:
                        st.write("Validation metrics", training_summary.validation_metrics)
                    if project.test_metrics is not None:
                        st.write("Test metrics", project.test_metrics)
                except Exception as exc:  # pragma: no cover - UI path
                    st.error(str(exc))

            st.subheader("Manual Training Controls")
            max_epochs = st.slider("Fine-tuning epochs", min_value=2, max_value=100, value=20)
            batch_size = st.slider("Batch size", min_value=8, max_value=128, value=32, step=8)
            learning_rate = st.select_slider(
                "Learning rate",
                options=[1e-4, 5e-4, 1e-3, 2e-3, 1e-2],
                value=1e-3,
            )
            refinement_cycles = st.slider(
                "Refinement cycles",
                min_value=1,
                max_value=1 if manual_rule_targets > 0 else 3,
                value=1,
            )
            stagewise = st.checkbox(
                "Use stage-wise pretraining",
                value=project.model_kind == "deep_fuzzy_feature_learning",
            )

            if st.button("Train Project", type="primary", use_container_width=True):
                try:
                    training_config = default_training_config(
                        project,
                        stagewise=stagewise,
                        refinement_cycles=refinement_cycles,
                        max_epochs=max_epochs,
                        batch_size=batch_size,
                        learning_rate=learning_rate,
                    )
                    training_summary = train(project, training_config=training_config)
                    st.session_state["project"] = project
                    st.success("Training finished.")
                    st.write("Training source", training_summary.source)
                    st.write("Train metrics", training_summary.train_metrics)
                    if training_summary.validation_metrics is not None:
                        st.write("Validation metrics", training_summary.validation_metrics)
                    if project.test_metrics is not None:
                        st.write("Test metrics", project.test_metrics)
                except Exception as exc:  # pragma: no cover - UI path
                    st.error(str(exc))

    project = st.session_state["project"]

    with explain_tab:
        st.subheader("Reports And Explainability")
        if project is None:
            st.info("Prepare and train a project first.")
        elif project.model is None:
            st.info("Train the current workspace first.")
        else:
            feature_frame = frame.drop(columns=[st.session_state["target_column"]])
            sample_count = min(5, len(feature_frame))
            sample_rows = st.slider("Samples to inspect", min_value=1, max_value=sample_count, value=min(2, sample_count))

            report_col, metrics_col = st.columns((3, 2))
            with report_col:
                st.text_area("Project report", project_report(project), height=280)
            with metrics_col:
                st.subheader("Metrics")
                st.json(summary(project))
                if project.training_summary is not None:
                    st.pyplot(plot_project_training_history(project))

            st.subheader("Model report")
            st.code(model_report(project), language="text")

            predictions = predict(project, feature_frame.head(sample_rows))
            st.subheader("Predictions")
            st.dataframe(pd.DataFrame(predictions, columns=["prediction"]), use_container_width=True)

            st.subheader("Sample explanations")
            st.code(explain(project, feature_frame.head(sample_rows), as_text=True), language="text")

            st.subheader("Dashboard payload")
            dashboard_payload = dashboard(project, feature_frame.head(1))
            st.json(dashboard_payload[0].to_dict())

            flow_left, flow_right = st.columns(2)
            with flow_left:
                st.subheader("Concept flow")
                st.code(concept_flow(project, feature_frame.head(1), as_text=True), language="text")
            with flow_right:
                st.subheader("Path concept flow")
                st.code(path_concept_flow(project, feature_frame.head(1), as_text=True), language="text")

            st.subheader("Rule chain flow")
            st.code(rule_chain_flow(project, feature_frame.head(1), as_text=True), language="text")


def _membership_editor_frame(variable, membership_kind: str | None = None):
    import pandas as pd

    membership = variable.membership
    kind = membership.kind.value if membership_kind is None else str(membership_kind)
    records = []

    if kind == "gaussian":
        source = membership if membership.kind.value == "gaussian" else None
        for index, term_name in enumerate(membership.term_names):
            records.append(
                {
                    "term_name": term_name,
                    "center": float(source.centers[index]) if source is not None else 0.0,
                    "spread": float(source.spreads[index]) if source is not None else 0.1,
                }
            )
    elif kind == "generalized_bell":
        source = membership if membership.kind.value == "generalized_bell" else None
        for index, term_name in enumerate(membership.term_names):
            records.append(
                {
                    "term_name": term_name,
                    "center": float(source.centers[index]) if source is not None else 0.0,
                    "width": float(source.widths[index]) if source is not None else 0.1,
                    "slope": float(source.slopes[index]) if source is not None else 2.0,
                }
            )
    elif kind == "triangular":
        source = membership if membership.kind.value == "triangular" else None
        for index, term_name in enumerate(membership.term_names):
            records.append(
                {
                    "term_name": term_name,
                    "left": float(source.left[index]) if source is not None else 0.0,
                    "center": float(source.center[index]) if source is not None else 0.5,
                    "right": float(source.right[index]) if source is not None else 1.0,
                }
            )
    else:
        source = membership if membership.kind.value == "trapezoidal" else None
        for index, term_name in enumerate(membership.term_names):
            records.append(
                {
                    "term_name": term_name,
                    "left": float(source.left[index]) if source is not None else 0.0,
                    "left_top": float(source.left_top[index]) if source is not None else 0.25,
                    "right_top": float(source.right_top[index]) if source is not None else 0.75,
                    "right": float(source.right[index]) if source is not None else 1.0,
                }
            )
    return pd.DataFrame.from_records(records)


def _guided_rule_builder_section(
    *,
    st,
    target: dict[str, object],
    rule_index: int,
    workspace_revision: int,
    existing_rule,
) -> dict[str, object]:
    variable_names = tuple(target.get("variable_names", ()))
    variable_terms = {
        str(name): tuple(values) for name, values in dict(target.get("variable_terms", {})).items()
    }
    default_rule = _default_guided_rule(target, rule_index=rule_index, existing_rule=existing_rule)
    rule_key = f"guided_rule::{workspace_revision}::{_rule_target_key(target)}::{rule_index}"

    with st.expander(f"Rule {rule_index + 1}: {default_rule['identifier']}", expanded=rule_index == 0):
        meta_left, meta_mid, meta_right, meta_last = st.columns(4)
        with meta_left:
            active = st.checkbox(
                "Active",
                value=bool(default_rule["active"]),
                key=f"{rule_key}::active",
            )
        with meta_mid:
            identifier = st.text_input(
                "Identifier",
                value=str(default_rule["identifier"]),
                key=f"{rule_key}::identifier",
            )
        with meta_right:
            weight = st.number_input(
                "Weight",
                value=float(default_rule["weight"]),
                format="%.6f",
                key=f"{rule_key}::weight",
            )
        with meta_last:
            aggregation = st.selectbox(
                "Aggregation",
                options=("product", "minimum"),
                index=("product", "minimum").index(default_rule["aggregation"])
                if default_rule["aggregation"] in ("product", "minimum")
                else 0,
                key=f"{rule_key}::aggregation",
            )

        default_antecedent_count = len(default_rule["antecedents"])
        max_arity = int(target.get("max_rule_arity") or max(1, len(variable_names)))
        antecedent_count = st.number_input(
            "Antecedent count",
            min_value=1,
            max_value=max(1, min(max_arity, len(variable_names) or 1)),
            value=max(1, min(default_antecedent_count, max(1, min(max_arity, len(variable_names) or 1)))),
            step=1,
            key=f"{rule_key}::antecedent_count",
        )

        antecedents = []
        for antecedent_index in range(int(antecedent_count)):
            default_antecedent = (
                default_rule["antecedents"][antecedent_index]
                if antecedent_index < len(default_rule["antecedents"])
                else _default_guided_antecedent(variable_names, variable_terms, antecedent_index)
            )
            left, right = st.columns(2)
            with left:
                variable_name = st.selectbox(
                    f"Antecedent {antecedent_index + 1} variable",
                    options=variable_names,
                    index=variable_names.index(default_antecedent["variable_name"])
                    if default_antecedent["variable_name"] in variable_names
                    else 0,
                    key=f"{rule_key}::antecedent::{antecedent_index}::variable",
                )
            term_options = variable_terms.get(variable_name, ())
            if not term_options:
                term_options = ("term_1",)
            with right:
                term_name = st.selectbox(
                    f"Antecedent {antecedent_index + 1} term",
                    options=term_options,
                    index=term_options.index(default_antecedent["term_name"])
                    if default_antecedent["term_name"] in term_options
                    else 0,
                    key=f"{rule_key}::antecedent::{antecedent_index}::term",
                )
            antecedents.append({"variable_name": variable_name, "term_name": term_name})

        st.caption("Consequents")
        consequent = {}
        for item in _consequent_entries_for_target(target, default_rule["consequent"]):
            left, right = st.columns((1, 2))
            with left:
                include = st.checkbox(
                    f"Use {item['key']}",
                    value=bool(item["enabled"]),
                    key=f"{rule_key}::consequent::{item['key']}::enabled",
                )
            with right:
                numeric_kwargs = {
                    "label": item["key"],
                    "value": float(item["value"]),
                    "format": "%.6f",
                    "key": f"{rule_key}::consequent::{item['key']}::value",
                }
                if item["bounded"]:
                    numeric_kwargs["min_value"] = 0.0
                    numeric_kwargs["max_value"] = 1.0
                value = st.number_input(**numeric_kwargs)
            if include:
                consequent[item["key"]] = float(value)

    return {
        "identifier": identifier.strip() or f"{target['block_name']}_rule_{rule_index + 1}",
        "antecedents": antecedents,
        "aggregation": aggregation,
        "weight": float(weight),
        "consequent": consequent,
        "layer_name": str(target["block_name"]),
        "active": bool(active),
    }


def _default_guided_rule(target: dict[str, object], *, rule_index: int, existing_rule) -> dict[str, object]:
    if existing_rule is not None:
        return {
            "identifier": existing_rule.identifier,
            "active": bool(existing_rule.active),
            "weight": float(existing_rule.weight),
            "aggregation": existing_rule.aggregation,
            "antecedents": [
                {"variable_name": item.variable_name, "term_name": item.term_name}
                for item in existing_rule.antecedents
            ],
            "consequent": dict(existing_rule.consequent),
        }

    variable_names = tuple(target.get("variable_names", ()))
    variable_terms = {
        str(name): tuple(values) for name, values in dict(target.get("variable_terms", {})).items()
    }
    antecedent_count = min(2, len(variable_names)) if variable_names else 1
    antecedents = [
        _default_guided_antecedent(variable_names, variable_terms, antecedent_index)
        for antecedent_index in range(antecedent_count)
    ]
    return {
        "identifier": f"{target['block_name']}_rule_{rule_index + 1}",
        "active": True,
        "weight": 0.5,
        "aggregation": "product",
        "antecedents": antecedents,
        "consequent": _default_consequent_for_target(target),
    }


def _default_guided_antecedent(
    variable_names: tuple[str, ...],
    variable_terms: dict[str, tuple[str, ...]],
    antecedent_index: int,
) -> dict[str, str]:
    if not variable_names:
        return {"variable_name": "variable_1", "term_name": "term_1"}
    variable_name = variable_names[min(antecedent_index, len(variable_names) - 1)]
    terms = variable_terms.get(variable_name, ("term_1",))
    return {"variable_name": variable_name, "term_name": terms[0]}


def _default_consequent_for_target(target: dict[str, object]) -> dict[str, float]:
    keys = _consequent_keys_for_target(target)
    if not keys:
        return {}
    first_key = keys[0]
    if target["layer_kind"] == "hidden":
        return {first_key: 0.8}
    return {first_key: 0.0}


def _consequent_entries_for_target(
    target: dict[str, object],
    current_consequent: dict[str, float],
) -> list[dict[str, object]]:
    entries = []
    known_keys = _consequent_keys_for_target(target)
    current = dict(current_consequent)
    for key in known_keys:
        entries.append(
            {
                "key": key,
                "enabled": key in current,
                "value": float(current.get(key, 0.8 if target["layer_kind"] == "hidden" else 0.0)),
                "bounded": target["layer_kind"] == "hidden",
            }
        )
    for key, value in current.items():
        if key in known_keys:
            continue
        entries.append(
            {
                "key": key,
                "enabled": True,
                "value": float(value),
                "bounded": target["layer_kind"] == "hidden",
            }
        )
    return entries


def _consequent_keys_for_target(target: dict[str, object]) -> list[str]:
    output_names = [str(name) for name in target.get("output_names", ())]
    if target["layer_kind"] == "hidden":
        return output_names

    variable_names = [str(name) for name in target.get("variable_names", ())]
    if len(output_names) <= 1:
        return ["bias", *variable_names]
    keys = [f"bias:{output_name}" for output_name in output_names]
    for output_name in output_names:
        keys.extend(f"{variable_name}:{output_name}" for variable_name in variable_names)
    return keys


def _variable_from_editor(
    *,
    variable_name: str,
    membership_kind: str,
    rows,
    value_range: tuple[float, float],
    data_type: str,
    role: str,
    normalization: str,
    gaussian_mf,
    gbell_mf,
    triangular_mf,
    trapezoidal_mf,
    make_variable,
):
    records = _editor_records(rows)
    if not records:
        raise ValueError("A variable must contain at least one membership term.")

    term_names = []
    for index, row in enumerate(records, start=1):
        term_name = str(row.get("term_name", "")).strip() or f"term_{index}"
        term_names.append(term_name)

    kind = str(membership_kind)
    if kind == "gaussian":
        membership = gaussian_mf(
            centers=tuple(_coerce_float(row.get("center"), label=f"center[{index}]") for index, row in enumerate(records)),
            spreads=tuple(_coerce_float(row.get("spread"), label=f"spread[{index}]") for index, row in enumerate(records)),
            term_names=tuple(term_names),
        )
    elif kind == "generalized_bell":
        membership = gbell_mf(
            centers=tuple(_coerce_float(row.get("center"), label=f"center[{index}]") for index, row in enumerate(records)),
            widths=tuple(_coerce_float(row.get("width"), label=f"width[{index}]") for index, row in enumerate(records)),
            slopes=tuple(_coerce_float(row.get("slope"), label=f"slope[{index}]") for index, row in enumerate(records)),
            term_names=tuple(term_names),
        )
    elif kind == "triangular":
        membership = triangular_mf(
            left=tuple(_coerce_float(row.get("left"), label=f"left[{index}]") for index, row in enumerate(records)),
            center=tuple(_coerce_float(row.get("center"), label=f"center[{index}]") for index, row in enumerate(records)),
            right=tuple(_coerce_float(row.get("right"), label=f"right[{index}]") for index, row in enumerate(records)),
            term_names=tuple(term_names),
        )
    elif kind == "trapezoidal":
        membership = trapezoidal_mf(
            left=tuple(_coerce_float(row.get("left"), label=f"left[{index}]") for index, row in enumerate(records)),
            left_top=tuple(
                _coerce_float(row.get("left_top"), label=f"left_top[{index}]") for index, row in enumerate(records)
            ),
            right_top=tuple(
                _coerce_float(row.get("right_top"), label=f"right_top[{index}]") for index, row in enumerate(records)
            ),
            right=tuple(_coerce_float(row.get("right"), label=f"right[{index}]") for index, row in enumerate(records)),
            term_names=tuple(term_names),
        )
    else:
        raise ValueError(f"Unsupported membership kind: {kind!r}.")

    low, high = float(value_range[0]), float(value_range[1])
    if low >= high:
        raise ValueError("Variable value_range requires min < max.")
    return make_variable(
        variable_name,
        membership,
        value_range=(low, high),
        data_type=data_type,
        role=role,
        normalization=normalization,
    )


def _rule_base_editor_frame(rule_base):
    import pandas as pd

    records = []
    for rule in rule_base.rules:
        records.append(
            {
                "active": bool(rule.active),
                "identifier": rule.identifier,
                "weight": float(rule.weight),
                "aggregation": rule.aggregation,
                "antecedents": _format_antecedents(rule),
                "consequent": _format_consequent(rule.consequent),
            }
        )
    return pd.DataFrame.from_records(records)


def _rule_base_from_editor_rows(rows, *, default_layer_name: str) -> object:
    from ruflex import RuleBaseSpec

    rules = []
    for row_index, row in enumerate(_editor_records(rows), start=1):
        if _blank_rule_row(row):
            continue
        identifier = str(row.get("identifier", "")).strip() or f"{default_layer_name}_rule_{row_index}"
        aggregation = str(row.get("aggregation", "product")).strip() or "product"
        weight = _coerce_float(row.get("weight", 0.5), label=f"weight[{row_index}]")
        antecedents = _parse_antecedents(str(row.get("antecedents", "")))
        consequent = _parse_consequent(str(row.get("consequent", "")))
        rules.append(
            {
                "identifier": identifier,
                "aggregation": aggregation,
                "weight": weight,
                "antecedents": antecedents,
                "consequent": consequent,
                "layer_name": default_layer_name,
                "active": bool(row.get("active", True)),
            }
        )
    return RuleBaseSpec.from_dict({"rules": rules})


def _blank_rule_row(row: dict[str, object]) -> bool:
    return not any(
        str(row.get(field, "")).strip()
        for field in ("identifier", "antecedents", "consequent")
    )


def _parse_antecedents(text: str) -> list[dict[str, str]]:
    chunks = [item.strip() for item in text.replace("\n", "&").split("&")]
    antecedents = []
    for chunk in chunks:
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError(f"Antecedent {chunk!r} must use the form variable=term.")
        variable_name, term_name = chunk.split("=", 1)
        variable_name = variable_name.strip()
        term_name = term_name.strip()
        if not variable_name or not term_name:
            raise ValueError(f"Antecedent {chunk!r} must include both variable and term names.")
        antecedents.append({"variable_name": variable_name, "term_name": term_name})
    return antecedents


def _parse_consequent(text: str) -> dict[str, float]:
    chunks = [item.strip() for item in text.replace("\n", ";").split(";")]
    consequent: dict[str, float] = {}
    for chunk in chunks:
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError(f"Consequent {chunk!r} must use the form key=value.")
        key, value = chunk.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Consequent {chunk!r} must include a key.")
        consequent[key] = _coerce_float(value, label=f"consequent[{key}]")
    return consequent


def _format_antecedents(rule) -> str:
    return " & ".join(f"{item.variable_name}={item.term_name}" for item in rule.antecedents)


def _format_consequent(consequent: dict[str, float]) -> str:
    return "; ".join(f"{key}={value}" for key, value in consequent.items())


def _editor_records(rows) -> list[dict[str, object]]:
    if hasattr(rows, "to_dict"):
        return list(rows.to_dict(orient="records"))
    return [dict(row) for row in rows]


def _coerce_float(value, *, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a numeric value.") from exc


def _prepare_workspace(
    *,
    frame,
    target_column: str,
    task_type: str,
    model_kind: str,
    term_count: int,
    validation_fraction: float,
    test_fraction: float,
    concept_width: int,
    block_size: int | None,
    hidden_stage_count: int | None,
    max_rules: int,
):
    from ruflex import attach_dataframe, configure_deep_model, configure_flat_model, infer_variables, new_project

    project = new_project("ruflex-workbench", task_type=task_type)
    attach_dataframe(
        project,
        frame,
        target_column=target_column,
        validation_fraction=validation_fraction,
        test_fraction=test_fraction,
    )
    infer_variables(project, term_count=term_count)
    if model_kind == "flat_neuro_fuzzy":
        configure_flat_model(project, n_concepts=concept_width, max_rules=max_rules)
    else:
        configure_deep_model(
            project,
            block_size=block_size or 2,
            hidden_stage_count=hidden_stage_count or 2,
            concept_width=concept_width,
            max_rules=max_rules,
        )
    return project


def _exported_metric_names(exported_studies: list[dict[str, object]] | tuple[dict[str, object], ...]) -> tuple[str, ...]:
    metric_names: set[str] = set()
    for item in exported_studies:
        for key in ("train_metrics", "validation_metrics", "test_metrics"):
            payload = item.get(key)
            if isinstance(payload, dict):
                metric_names.update(str(name) for name in payload)
    preferred_order = ("rmse", "mse", "mae", "r2", "accuracy", "precision", "recall", "f1")
    ordered = [name for name in preferred_order if name in metric_names]
    tail = sorted(name for name in metric_names if name not in preferred_order)
    return tuple(ordered + tail)


def _benchmark_result_metric_names(results: list[dict[str, object]] | tuple[dict[str, object], ...]) -> tuple[str, ...]:
    metric_names: set[str] = set()
    for row in results:
        for key in row:
            if key.startswith(("train_", "validation_", "test_")) and key not in {
                "training_preset",
                "training_source",
                "training_preset_override",
            }:
                metric_names.add(str(key))
    preferred_order = (
        "test_rmse",
        "test_mse",
        "test_mae",
        "test_r2",
        "test_accuracy",
        "test_precision",
        "test_recall",
        "test_f1",
        "validation_rmse",
        "validation_mse",
        "validation_mae",
        "validation_r2",
        "validation_accuracy",
        "validation_precision",
        "validation_recall",
        "validation_f1",
    )
    ordered = [name for name in preferred_order if name in metric_names]
    tail = sorted(name for name in metric_names if name not in ordered)
    return tuple(ordered + tail)


def _benchmark_metric_higher_is_better(metric_name: str, goal: str) -> bool:
    if goal == "maximize":
        return True
    if goal == "minimize":
        return False
    return metric_name.lower().endswith(("r2", "accuracy", "precision", "recall", "f1"))


def _format_rule_target(target: dict[str, object]) -> str:
    if target["layer_kind"] == "decision":
        return f"decision | {target['block_name']}"
    return f"{target['stage_name']} | {target['block_name']}"


def _rule_target_key(target: dict[str, object]) -> str:
    if target["layer_kind"] == "decision":
        return f"decision::{target['block_name']}"
    return f"{target['stage_name']}::{target['block_name']}"


def _current_rule_base(project, *, target, get_block_rule_base, get_decision_rule_base):
    if target["layer_kind"] == "decision":
        return get_decision_rule_base(project)
    return get_block_rule_base(project, target["block_name"], stage_name=target["stage_name"])


def _assign_rule_base(project, *, target, rule_base, set_block_rule_base, set_decision_rule_base):
    if target["layer_kind"] == "decision":
        set_decision_rule_base(project, rule_base)
        return
    set_block_rule_base(project, target["block_name"], rule_base, stage_name=target["stage_name"])


def _build_demo_frame():
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(11)
    samples = 256
    x1 = rng.uniform(0.0, 1.0, size=samples)
    x2 = rng.uniform(0.0, 1.0, size=samples)
    x3 = rng.uniform(0.0, 1.0, size=samples)
    x4 = rng.uniform(0.0, 1.0, size=samples)
    y = 0.45 * np.sin(np.pi * x1 * x2) + 0.30 * (x3 * x4) + 0.15 * x1
    return pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "x4": x4, "y": y})
