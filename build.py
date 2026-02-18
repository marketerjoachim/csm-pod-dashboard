#!/usr/bin/env python3
"""
CSM Pod Dashboard Builder
Parses Attio CRM data files, computes LTV model, generates HTML dashboard.
"""

import json
import re
import os
import shutil
from datetime import datetime, date
from sub_start_dates import SUBSCRIPTION_START_DATES, SUBSCRIPTION_CHURN_DATA

# ─── Onboarding Queue (extracted from Attio) ─────────────────────────────────
# Supplemental onboarding records not in main workspace data files
ONBOARDING_QUEUE_EXTRA = [
    {"record_id": "54cc5e11-c8ad-4aee-8934-468c70422686", "name": "Aleavia", "pod": "Marcus+Martin", "plan": "Performance", "arr": 47988, "mrr": 3999, "onboarding_date": "2026-02-18", "start_date": "2026-02-09", "last_payment": "2026-02-09", "renewal_date": "2026-03-09", "billing_cycle": "Monthly", "sales_rep": "William Habert"},
    {"record_id": "dbd807b7-1077-4e84-92b6-726b2b089c04", "name": "motocross4u.com", "pod": "Aimy+Espen", "plan": "Pro", "arr": 28788, "mrr": 2399, "onboarding_date": "2026-02-18", "start_date": "2026-01-27", "last_payment": "2026-01-27", "renewal_date": "2026-02-27", "billing_cycle": "Monthly", "sales_rep": "Kenneth Eriksen"},
    {"record_id": "a11461e3-41d3-4852-9bde-10b82085dc14", "name": "fjorda.com", "pod": "Aimy+Espen", "plan": "Growth", "arr": 12000, "mrr": 1000, "onboarding_date": "2026-02-18", "start_date": "2026-02-16", "last_payment": "2026-02-16", "renewal_date": "2026-03-16", "billing_cycle": "Monthly", "sales_rep": "Victor Svalastog"},
    {"record_id": "e6e89eae-d286-44e5-b1b9-282c7b23bf70", "name": "Company of Scott McKearn", "pod": "Nicklas+Hamsa", "plan": "Growth", "arr": 12000, "mrr": 1000, "onboarding_date": "2026-02-18", "start_date": "2026-02-04", "last_payment": "2026-02-04", "renewal_date": "2026-03-04", "billing_cycle": "Monthly", "sales_rep": "Andreas Aasen"},
    {"record_id": "4c5b0e94-1d3c-404b-984f-bcf5db2fc8f6", "name": "equacare.com.au", "pod": "Marcus+Martin", "plan": "Pro", "arr": 28788, "mrr": 2399, "onboarding_date": "2026-02-18", "start_date": "2026-02-12", "last_payment": "2026-02-12", "renewal_date": "2026-03-12", "billing_cycle": "Monthly", "sales_rep": "Omid Aboui"},
    {"record_id": "bb0172b5-5057-48dc-bd9c-84b6cfb50ed3", "name": "lilcactus.com", "pod": "Marcus+Martin", "plan": "Pro", "arr": 28788, "mrr": 2399, "onboarding_date": "2026-02-18", "start_date": "2026-02-13", "last_payment": "2026-02-13", "renewal_date": "2026-03-13", "billing_cycle": "Monthly", "sales_rep": "Andreas Aasen"},
]

# ─── Churn Context (extracted from Attio calls/emails/CSM fields) ────────────
# record_id -> {summary, source}
CHURN_CONTEXT = {
    "31f36ad0-1ee1-53ba-bb70-884b70900da9": {
        "summary": "Ghosted — unable to reach client, no campaigns running, doesn't open emails",
        "source": "csm_field",
    },
    "3d95ba46-68d0-5e96-99e7-36ab16f57f9b": {
        "summary": "Persistent issues integrating Meta/Google ad accounts, never got campaigns live",
        "source": "csm_field",
    },
    "47da0b32-b1d9-5bdf-a8d9-5d45c85813fe": {
        "summary": "Severe capital constraints (partner health crisis), unable to fund ad spend despite wanting to continue",
        "source": "call",
    },
    "686b3476-4e8f-4a29-93ff-577949ccb041": {
        "summary": "Pausing due to budget constraints, wants to rebuild website first; plans to return mid-March",
        "source": "call",
    },
    "3bf59165-d9f3-40a4-aaca-89fc5f920de2": {
        "summary": "Near-zero ROI after ~$2K ad spend, poor creative quality, CSM handover left account neglected with ads not running, repeated escalations unaddressed",
        "source": "email",
    },
}

# ─── Configuration ──────────────────────────────────────────────────────────────

TODAY = date(2026, 2, 18)
YESTERDAY = date(2026, 2, 17)
YESTERDAY_STR = "2026-02-17"

DATA_DIR = os.path.expanduser(
    "~/.claude/projects/-Users-jmow/7cbfc0d6-2d21-47cb-82df-71bfbe25e5da/tool-results/"
)

DATA_FILES = {
    "mcp-claude_ai_Attio-list-records-1771365830014.txt": "adec27dd-d669-4b66-997d-a69d849bd89e",  # Marcus
    "mcp-claude_ai_Attio-list-records-1771365829271.txt": "fde0e89d-1e64-40e7-b0aa-20dcb447654e",  # Martin
    "mcp-claude_ai_Attio-list-records-1771365813580.txt": "3fe5674b-9030-42ac-9a01-00b767b1da54",  # Sebastian
    "mcp-claude_ai_Attio-list-records-1771365813430.txt": "9b18f459-0067-4b48-8aac-ee6acf7f344d",  # Daniel
    "mcp-claude_ai_Attio-list-records-1771365814869.txt": "711568b9-561b-4bdf-aa34-a92a36362e21",  # Nicklas
}

CSM_MAP = {
    "adec27dd-d669-4b66-997d-a69d849bd89e": ("Marcus", "FE", "Marcus+Martin"),
    "fde0e89d-1e64-40e7-b0aa-20dcb447654e": ("Martin", "BE", "Marcus+Martin"),
    "3fe5674b-9030-42ac-9a01-00b767b1da54": ("Sebastian", "FE", "Sebastian+Daniel"),
    "9b18f459-0067-4b48-8aac-ee6acf7f344d": ("Daniel", "BE", "Sebastian+Daniel"),
    "5ffeee2d-f0be-4d21-be37-b7296833c338": ("Aimy", "FE", "Aimy+Espen"),
    "7a3a0d48-78bb-4d1f-8388-e9752813439a": ("Espen", "BE", "Aimy+Espen"),
    "711568b9-561b-4bdf-aa34-a92a36362e21": ("Nicklas", "FE", "Nicklas+Hamsa"),
    "d5acc899-dfef-4943-84f6-359b04cdc162": ("Hamsa", "BE", "Nicklas+Hamsa"),
}

PLAN_ARR = {
    "Enterprise": 50000,
    "Performance": 48000,
    "Pro": 25000,
    "Growth": 9000,
    "Lite": 6000,
    "Starter": 5000,
}

PW_HASH = "b83f9851aaf52cff85bd8b4e2c63a8c97fec407e8249d78cc27e1f8581915f61"

OUTPUT_PATH = os.path.expanduser("~/csm-pod-dashboard/public/index.html")
DOCS_PATH = os.path.expanduser("~/csm-pod-dashboard/docs/index.html")

# ─── Hardcoded Data ─────────────────────────────────────────────────────────────

AIMY_DATA = [
    {'record_id':'132747be-d0a8-4194-8e1c-6f6c12abc989','name':'House of Walton','plan':'Growth','health_status':'2','est_ltv':'1','workspace_id':'sub_1RsCT7FopWoUwtLcL13BvRgx','shopify_sales_3':'USD 2,408.25','roas':3.2,'atd_roas':1.11,'amount_of_campaigns_live':3,'days_without_active_campaign':0,'comment':'Intro call planned','churn_risk_reason':None,'soft_churn':None,'active_status':['Extra care'],'created_at':'2025-08-04','onboarding_date':None,'manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'5538ff2d-e66e-4fb8-8268-e9e1cd3719aa','name':'Cheekbone Beauty','plan':'Lite','health_status':None,'est_ltv':None,'workspace_id':'sub_1Rb1ixFopWoUwtLcWkMeZN4o','shopify_sales_3':'USD 100,831.79','roas':None,'atd_roas':2.6,'amount_of_campaigns_live':0,'days_without_active_campaign':15,'comment':'Need to top up waller','churn_risk_reason':None,'soft_churn':None,'active_status':['Extra care'],'created_at':'2025-08-04','onboarding_date':None,'manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':'Maybe','upsell_arr_increase':'USD 22,792.00','rev_share_agreement':None},
    {'record_id':'60634c40-ab4a-4d14-abd3-67895e2d08e0','name':'Duralex USA','plan':'Growth','health_status':'5','est_ltv':'2','workspace_id':'sub_1RyDoIFopWoUwtLct4g9SoYo','shopify_sales_3':'USD 126,475.15','roas':7.67,'atd_roas':12.65,'amount_of_campaigns_live':1,'days_without_active_campaign':0,'comment':'Good as it is','churn_risk_reason':None,'soft_churn':None,'active_status':['Healthy'],'created_at':'2025-08-04','onboarding_date':None,'manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':'USD 16,788.00','rev_share_agreement':None},
    {'record_id':'6ea04561-67f6-4091-8196-6f128cc1465b','name':'the friend of Pablo \u00f3ptica','plan':'Pro','health_status':'5','est_ltv':'2','workspace_id':'sub_1SvFG4FopWoUwtLcWYc29Uf4','shopify_sales_3':'USD 1,510.22','roas':0,'atd_roas':0,'amount_of_campaigns_live':4,'days_without_active_campaign':0,'comment':'Testing phase for campaigns','churn_risk_reason':None,'soft_churn':None,'active_status':['Healthy'],'created_at':'2025-08-04','onboarding_date':'2026-01-27','manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'7b0e0a0d-73ec-5710-97cd-29ce467311d3','name':'MXTology','plan':'Lite','health_status':'2','est_ltv':None,'workspace_id':'sub_1QzQS9FopWoUwtLc2aOk6euW','shopify_sales_3':'USD 1,797.10','roas':0,'atd_roas':0.56,'amount_of_campaigns_live':1,'days_without_active_campaign':0,'comment':'Waiting for his email with details about what he wants for the new visuals','churn_risk_reason':None,'soft_churn':'true','active_status':['Healthy'],'created_at':'2025-08-04','onboarding_date':None,'manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'a11461e3-41d3-4852-9bde-10b82085dc14','name':'fjorda.com','plan':'Growth','health_status':None,'est_ltv':'1','workspace_id':'sub_1T1OLXFopWoUwtLcaZmdtIDJ','shopify_sales_3':None,'roas':None,'atd_roas':None,'amount_of_campaigns_live':None,'days_without_active_campaign':None,'comment':'','churn_risk_reason':None,'soft_churn':None,'active_status':[],'created_at':'2025-08-04','onboarding_date':'2026-01-27','manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'b16642f5-d93c-51fd-a910-495e954fda3b','name':'LATRAVLA','plan':'Growth','health_status':'4','est_ltv':'2','workspace_id':'sub_1SwvZnFopWoUwtLcipwqo0zE','shopify_sales_3':None,'roas':0,'atd_roas':0,'amount_of_campaigns_live':2,'days_without_active_campaign':0,'comment':'Good as it is | Creatives ordered','churn_risk_reason':None,'soft_churn':None,'active_status':['Healthy'],'created_at':'2025-08-04','onboarding_date':'2026-01-27','manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'b1c3db34-db0c-4211-ba06-2c15e8dfad5b','name':'Peonie Collection','plan':'Growth','health_status':None,'est_ltv':'1','workspace_id':'sub_1Szz8OFopWoUwtLcG5hC2rNZ','shopify_sales_3':'USD 200.46','roas':None,'atd_roas':None,'amount_of_campaigns_live':0,'days_without_active_campaign':None,'comment':'','churn_risk_reason':None,'soft_churn':None,'active_status':[],'created_at':'2025-08-04','onboarding_date':None,'manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'bc585cab-54c5-4ce6-a4a7-65f725fc28d0','name':'Yah Cha','plan':'Growth','health_status':'2','est_ltv':'1','workspace_id':'sub_1SAhJuFopWoUwtLchgNaXFxQ','shopify_sales_3':'USD 1,467.90','roas':0.62,'atd_roas':0.36,'amount_of_campaigns_live':5,'days_without_active_campaign':0,'comment':'Really need to turn this account around!','churn_risk_reason':None,'soft_churn':None,'active_status':['Churn risk'],'created_at':'2025-08-04','onboarding_date':None,'manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'c1cc9697-0ce1-4053-93d9-62cb555852e9','name':'DearlyDone','plan':'Growth','health_status':'1','est_ltv':'1','workspace_id':'sub_1StH53FopWoUwtLcTBMf7mrz','shopify_sales_3':None,'roas':None,'atd_roas':None,'amount_of_campaigns_live':0,'days_without_active_campaign':None,'comment':'Victor is jumping in. Need someone that can fix his pixel tracking issue. But ghosting us','churn_risk_reason':None,'soft_churn':None,'active_status':['Ghosting','Blocker'],'created_at':'2025-08-04','onboarding_date':'2026-01-27','manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'c3ed605d-8c77-5dd3-ad9c-9f465e3be28f','name':'Artamine','plan':'Growth','health_status':'5','est_ltv':'2','workspace_id':'sub_1SzZ4bFopWoUwtLcDtCpWGZY','shopify_sales_3':None,'roas':0,'atd_roas':0,'amount_of_campaigns_live':0,'days_without_active_campaign':2,'comment':'Good as it is for now','churn_risk_reason':None,'soft_churn':None,'active_status':[],'created_at':'2025-08-04','onboarding_date':None,'manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'d108acd6-e1da-4b27-b11d-4a8596478766','name':'Nightollie','plan':'Growth','health_status':None,'est_ltv':'1','workspace_id':'sub_1RlNj3FopWoUwtLcZyYGJMjp','shopify_sales_3':'USD 8,691.48','roas':None,'atd_roas':0,'amount_of_campaigns_live':0,'days_without_active_campaign':69,'comment':'Aimy / Sebastian','churn_risk_reason':None,'soft_churn':None,'active_status':[],'created_at':'2025-08-04','onboarding_date':None,'manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':'Yes - Referral','upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'d920fb32-f0a7-4948-ba70-7fac9859dfec','name':'Cavvalure','plan':'Pro','health_status':'3','est_ltv':'2','workspace_id':'sub_1SzwErFopWoUwtLcPiFgJ1oq','shopify_sales_3':'USD 0.00','roas':0,'atd_roas':0,'amount_of_campaigns_live':1,'days_without_active_campaign':0,'comment':'','churn_risk_reason':None,'soft_churn':None,'active_status':[],'created_at':'2025-08-04','onboarding_date':'2026-01-27','manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'dbd807b7-1077-4e84-92b6-726b2b089c04','name':'motocross4u.com','plan':'Pro','health_status':None,'est_ltv':'2','workspace_id':'sub_1SuBGiFopWoUwtLcxgVF01C5','shopify_sales_3':None,'roas':None,'atd_roas':None,'amount_of_campaigns_live':None,'days_without_active_campaign':None,'comment':'','churn_risk_reason':None,'soft_churn':None,'active_status':[],'created_at':'2025-08-04','onboarding_date':'2026-01-27','manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'e0b7539c-dc24-43e6-8d48-0cf544e62890','name':'AmericUrn','plan':'Growth','health_status':'1','est_ltv':'1','workspace_id':'sub_1StH49FopWoUwtLcEOi7WvEw','shopify_sales_3':'USD 44,096.88','roas':0,'atd_roas':0,'amount_of_campaigns_live':1,'days_without_active_campaign':0,'comment':'Victor is jumping in. Need someone that can fix his pixel tracking issue. But ghosting us','churn_risk_reason':None,'soft_churn':None,'active_status':['Blocker','Ghosting'],'created_at':'2025-08-04','onboarding_date':'2026-01-27','manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'f58ed4b7-d252-4d3c-a423-e7f43177026f','name':'Innovative Pet Lab','plan':'Growth','health_status':'3','est_ltv':'1','workspace_id':'sub_1SxBw3FopWoUwtLcUfOImyUa','shopify_sales_3':'USD 8,340.43','roas':0.05,'atd_roas':0.05,'amount_of_campaigns_live':1,'days_without_active_campaign':0,'comment':'Too early to tell what they need','churn_risk_reason':None,'soft_churn':None,'active_status':['Healthy'],'created_at':'2025-08-04','onboarding_date':'2026-01-27','manager_id':'5ffeee2d-f0be-4d21-be37-b7296833c338','csm':'Aimy','pod':'Aimy+Espen','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
]

HAMSA_DATA = [
    {'record_id':'65d3e7c3-431c-4bb2-85fd-df8487b6c344','name':'Barisi International','plan':'Growth','health_status':None,'est_ltv':'2','workspace_id':'sub_1Sx31qFopWoUwtLcpBuFD3z2','shopify_sales_3':None,'roas':None,'atd_roas':None,'amount_of_campaigns_live':0,'days_without_active_campaign':None,'comment':'','churn_risk_reason':None,'soft_churn':None,'active_status':['Healthy'],'created_at':'2026-01-25','onboarding_date':None,'manager_id':'d5acc899-dfef-4943-84f6-359b04cdc162','csm':'Hamsa','pod':'Nicklas+Hamsa','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'8e9df40a-15d6-430b-9032-8e00b0b0c89b','name':'Vesalix','plan':'Growth','health_status':'3','est_ltv':'1','workspace_id':'sub_1SsFmvFopWoUwtLcTFttyVdu','shopify_sales_3':'USD 109.85','roas':None,'atd_roas':0,'amount_of_campaigns_live':0,'days_without_active_campaign':8,'comment':'','churn_risk_reason':'Cancelled / overdue','soft_churn':None,'active_status':[],'created_at':'2026-01-25','onboarding_date':'2026-01-23','manager_id':'d5acc899-dfef-4943-84f6-359b04cdc162','csm':'Hamsa','pod':'Nicklas+Hamsa','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'92120151-2a90-405a-bf39-c122abe1efe1','name':'Elite Thread Co','plan':'Growth','health_status':'3','est_ltv':'2','workspace_id':'sub_1Ss0CBFopWoUwtLcsYmSmYII','shopify_sales_3':'USD 8,803.99','roas':4.35,'atd_roas':3.47,'amount_of_campaigns_live':1,'days_without_active_campaign':0,'comment':'','churn_risk_reason':None,'soft_churn':None,'active_status':[],'created_at':'2026-01-25','onboarding_date':None,'manager_id':'d5acc899-dfef-4943-84f6-359b04cdc162','csm':'Hamsa','pod':'Nicklas+Hamsa','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'b5bc95c7-e965-5dec-b479-7ace6dea8a5f','name':'Cossino','plan':'Growth','health_status':'5','est_ltv':'1','workspace_id':'sub_1Srk9MFopWoUwtLcyWXrJ4TX','shopify_sales_3':'USD 2,837.36','roas':1.02,'atd_roas':0.37,'amount_of_campaigns_live':3,'days_without_active_campaign':0,'comment':'','churn_risk_reason':None,'soft_churn':None,'active_status':[],'created_at':'2026-01-25','onboarding_date':'2026-01-23','manager_id':'d5acc899-dfef-4943-84f6-359b04cdc162','csm':'Hamsa','pod':'Nicklas+Hamsa','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'b6ba0f85-9344-4168-8b7d-1088809e2543','name':'Bean Bros','plan':'Growth','health_status':None,'est_ltv':'2','workspace_id':'sub_1SsL64FopWoUwtLcbRUHqr1J','shopify_sales_3':'USD 55,784.40','roas':None,'atd_roas':None,'amount_of_campaigns_live':0,'days_without_active_campaign':None,'comment':'','churn_risk_reason':None,'soft_churn':None,'active_status':[],'created_at':'2026-01-25','onboarding_date':None,'manager_id':'d5acc899-dfef-4943-84f6-359b04cdc162','csm':'Hamsa','pod':'Nicklas+Hamsa','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'c086cad9-9176-5c70-aef6-12fbad9eba2d','name':'Zindiak','plan':'Lite','health_status':'5','est_ltv':'1','workspace_id':'sub_1QnPCOFopWoUwtLcbE923LQa','shopify_sales_3':'USD 56,966.64','roas':None,'atd_roas':0,'amount_of_campaigns_live':0,'days_without_active_campaign':75,'comment':'Handed over to nicklas','churn_risk_reason':'Cancelled / overdue','soft_churn':None,'active_status':['Churn risk','Extra care'],'created_at':'2026-01-25','onboarding_date':None,'manager_id':'d5acc899-dfef-4943-84f6-359b04cdc162','csm':'Hamsa','pod':'Nicklas+Hamsa','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
    {'record_id':'ec2325e8-a474-4400-9e0a-6638cde68719','name':'The A Fragrance','plan':'Growth','health_status':'3','est_ltv':'2','workspace_id':'sub_1StXtxFopWoUwtLcP8cFv1zV','shopify_sales_3':'USD 6,811.68','roas':2.01,'atd_roas':2.01,'amount_of_campaigns_live':1,'days_without_active_campaign':0,'comment':'','churn_risk_reason':None,'soft_churn':None,'active_status':[],'created_at':'2026-01-25','onboarding_date':None,'manager_id':'d5acc899-dfef-4943-84f6-359b04cdc162','csm':'Hamsa','pod':'Nicklas+Hamsa','bull':None,'upsell_arr_increase':None,'rev_share_agreement':None},
]


# ─── Parsing ────────────────────────────────────────────────────────────────────

def parse_shopify_usd(val):
    """Parse 'USD 1,234.56' or similar to float."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    val = str(val).strip().strip('"')
    val = val.replace("USD ", "").replace("USD", "").replace(",", "").strip()
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0


def parse_date_str(val):
    """Parse various date formats to 'YYYY-MM-DD' string or None."""
    if val is None or val == "" or val == "null":
        return None
    val = str(val).strip().strip('"')
    # Try "Monday, 2026-02-09 21:06:40" format
    m = re.search(r"(\d{4}-\d{2}-\d{2})", val)
    if m:
        return m.group(1)
    return None


def parse_attio_text(text, file_manager_id):
    """Parse the Attio text format into a list of record dicts."""
    records = []
    # Split on record boundaries
    parts = text.split("\n  - record_id: ")
    for part in parts[1:]:  # Skip the header
        lines = part.split("\n")
        record_id = lines[0].strip()
        rec = {"record_id": record_id}

        i = 1
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                i += 1
                continue

            # Skip 'attributes:' header
            if stripped == "attributes:":
                i += 1
                continue

            # Check if this is a field line (6 spaces indent = attribute level)
            if line.startswith("      "):
                # Check for nested field (next line has 8 spaces)
                if ":" in stripped:
                    key_part, _, val_part = stripped.partition(":")
                    key = key_part.strip()
                    val = val_part.strip()

                    # Handle array fields like active_status[2]: Churn risk,Extra care
                    array_match = re.match(r"(\w+)\[\d+\](\{[^}]*\})?", key)
                    if array_match:
                        base_key = array_match.group(1)
                        # Skip complex array fields we don't need
                        if base_key in ("workspaces", "people", "subscriptions", "designer", "previous_csm"):
                            # Skip continuation lines
                            i += 1
                            while i < len(lines) and lines[i].startswith("        "):
                                i += 1
                            continue
                        # Parse simple array values
                        if val:
                            rec[base_key] = [v.strip() for v in val.split(",")]
                        else:
                            rec[base_key] = []
                            # Read continuation lines
                            i += 1
                            while i < len(lines) and lines[i].startswith("        "):
                                rec[base_key].append(lines[i].strip())
                                i += 1
                            continue
                    elif key in ("manager", "be_csm", "created_by", "company"):
                        # Nested object - read next line(s) for value
                        i += 1
                        nested = {}
                        while i < len(lines) and lines[i].startswith("        "):
                            nline = lines[i].strip()
                            if ":" in nline:
                                nk, _, nv = nline.partition(":")
                                nested[nk.strip()] = nv.strip()
                            i += 1
                        if key == "manager":
                            rec["manager_id"] = nested.get("workspace_membership_id", "")
                        elif key == "be_csm":
                            rec["be_csm_id"] = nested.get("workspace_membership_id", "")
                        continue
                    else:
                        # Simple field
                        # Strip quotes
                        if val.startswith('"') and val.endswith('"'):
                            val = val[1:-1]
                        if val == "null" or val == "":
                            val = None
                        rec[key] = val

            i += 1

        # Determine CSM assignment
        manager_id = rec.get("manager_id", "")
        be_csm_id = rec.get("be_csm_id", "")

        # Use manager first, fall back to be_csm, then file's manager
        csm_id = manager_id if manager_id in CSM_MAP else (
            be_csm_id if be_csm_id in CSM_MAP else file_manager_id
        )

        if csm_id in CSM_MAP:
            csm_name, csm_role, pod = CSM_MAP[csm_id]
            rec["csm"] = csm_name
            rec["pod"] = pod
        else:
            rec["csm"] = "Unknown"
            rec["pod"] = "Unknown"

        records.append(rec)

    return records


def normalize_record(rec, trust_created_at=True):
    """Normalize a parsed record into a standard dict for LTV computation.

    trust_created_at: If False, created_at is ignored (file-parsed records have
    a uniform CRM sync date that is not meaningful as customer start date).
    """
    name = rec.get("name", "Unknown")
    plan = rec.get("plan", "Growth")
    health_str = rec.get("health_status")
    health = None
    if health_str is not None:
        try:
            health = int(health_str)
        except (ValueError, TypeError):
            health = None

    est_ltv_str = rec.get("est_ltv")
    est_ltv = None
    if est_ltv_str is not None:
        try:
            est_ltv = int(str(est_ltv_str).strip().strip('"'))
        except (ValueError, TypeError):
            est_ltv = None

    workspace_id = rec.get("workspace_id", "")
    shopify_raw = rec.get("shopify_sales_3")
    shopify = parse_shopify_usd(shopify_raw)

    roas_raw = rec.get("roas")
    try:
        roas = float(roas_raw) if roas_raw is not None else None
    except (ValueError, TypeError):
        roas = None

    atd_roas_raw = rec.get("atd_roas")
    try:
        atd_roas = float(atd_roas_raw) if atd_roas_raw is not None else None
    except (ValueError, TypeError):
        atd_roas = None

    campaigns_raw = rec.get("amount_of_campaigns_live")
    try:
        campaigns = int(campaigns_raw) if campaigns_raw is not None else 0
    except (ValueError, TypeError):
        campaigns = 0

    days_inactive_raw = rec.get("days_without_active_campaign")
    try:
        days_inactive = int(days_inactive_raw) if days_inactive_raw is not None else 0
    except (ValueError, TypeError):
        days_inactive = 0

    comment = rec.get("comment", "") or ""
    churn_risk_reason = rec.get("churn_risk_reason")
    soft_churn_raw = rec.get("soft_churn")
    soft_churn = soft_churn_raw in ("true", True, "True")

    lost_reason = rec.get("lost_reason") or ""
    churn_comment = rec.get("churn_comment", "") or ""

    active_status = rec.get("active_status", [])
    if isinstance(active_status, str):
        active_status = [s.strip() for s in active_status.split(",") if s.strip()]

    created_at_str = parse_date_str(rec.get("created_at")) if trust_created_at else None
    onboarding_date_str = parse_date_str(rec.get("onboarding_date"))

    bull_raw = rec.get("bull")
    if isinstance(bull_raw, list):
        bull = bull_raw[0] if bull_raw else None
    else:
        bull = bull_raw

    upsell_raw = rec.get("upsell_arr_increase")
    upsell_arr = parse_shopify_usd(upsell_raw) if upsell_raw else 0

    rev_share_raw = rec.get("rev_share_agreement")
    rev_share = rev_share_raw in ("true", True, "True")

    return {
        "record_id": rec.get("record_id", ""),
        "name": name,
        "plan": plan,
        "health": health,
        "est_ltv": est_ltv,
        "workspace_id": workspace_id,
        "shopify": shopify,
        "roas": roas,
        "atd_roas": atd_roas,
        "campaigns": campaigns,
        "days_inactive": days_inactive,
        "comment": comment,
        "churn_risk_reason": churn_risk_reason,
        "soft_churn": soft_churn,
        "active_status": active_status,
        "created_at": created_at_str,
        "onboarding_date": onboarding_date_str,
        "csm": rec.get("csm", "Unknown"),
        "pod": rec.get("pod", "Unknown"),
        "bull": bull,
        "upsell_arr": upsell_arr,
        "rev_share": rev_share,
        "lost_reason": lost_reason,
        "churn_comment": churn_comment,
    }


# ─── LTV Model ─────────────────────────────────────────────────────────────────

def compute_tenure_months(start_date_str):
    """Compute months since start date."""
    if not start_date_str:
        return None
    try:
        sd = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        delta = TODAY - sd
        return max(0, delta.days / 30.44)
    except (ValueError, TypeError):
        return None


def compute_ltv(ws):
    """Compute 2yr LTV, priority, tier, signals for a workspace."""
    plan = ws["plan"]
    arr = PLAN_ARR.get(plan, 9000)
    health = ws["health"]
    atd_roas = ws["atd_roas"] or 0
    shopify = ws["shopify"]
    campaigns = ws["campaigns"]
    days_inactive = ws["days_inactive"]
    churn_risk_reason = ws["churn_risk_reason"]
    soft_churn = ws["soft_churn"]
    active_status = ws["active_status"]
    bull = ws["bull"]
    upsell_arr = ws["upsell_arr"]
    est_ltv = ws["est_ltv"]

    # Start date: use subscription start_date from Stripe, fall back to onboarding_date
    record_id = ws["record_id"]
    start_date = SUBSCRIPTION_START_DATES.get(record_id) or ws["onboarding_date"]
    tenure_months = compute_tenure_months(start_date)

    # --- Retention ---
    ret_map = {5: 0.92, 4: 0.82, 3: 0.60, 2: 0.40, 1: 0.25}
    ret = ret_map.get(health, 0.65)

    # Churn penalties
    has_churn_risk = any("Churn risk" in str(s) for s in active_status)
    if churn_risk_reason or soft_churn or has_churn_risk:
        ret *= 0.7

    # Idle penalty
    if days_inactive >= 20:
        penalty = min(0.15, (days_inactive - 20) * 0.002)
        ret *= (1 - penalty)

    # Tenure boost
    if tenure_months is not None:
        if tenure_months < 1:
            ret *= 0.90
        elif tenure_months < 3:
            ret *= 1.0
        elif tenure_months < 6:
            ret *= 1.05
        elif tenure_months < 12:
            ret *= 1.10
        elif tenure_months < 18:
            ret *= 1.15
        else:
            ret *= 1.20

    # Cap retention at 0.95
    ret = min(ret, 0.95)

    # --- Growth ---
    if atd_roas >= 8:
        growth = 2.0
    elif atd_roas >= 5:
        growth = 1.7
    elif atd_roas >= 2:
        growth = 1.3
    elif atd_roas >= 1:
        growth = 1.1
    else:
        growth = 1.0

    # Zero campaigns + idle
    if campaigns == 0 and days_inactive >= 20:
        growth = 0.5

    # Shopify boost
    if shopify >= 500000:
        growth = max(growth, 2.5)
    elif shopify >= 100000:
        growth = max(growth, 1.8)
    elif shopify >= 50000:
        growth = max(growth, 1.3)

    # Bull/Time=ROAS
    if bull and ("Yes" in str(bull) or "Maybe" in str(bull)):
        growth = max(growth, 1.5)

    # Customer Score multiplier (est_ltv field)
    if est_ltv == 3:
        growth *= 1.4
    elif est_ltv == 2:
        growth *= 1.15
    # Score 1 or None: growth *= 1.0 (no change)

    # --- Effort ---
    effort = 1.0
    has_blocker = any("Blocker" in str(s) for s in active_status)
    has_ghosting = any("Ghosting" in str(s) for s in active_status)
    has_csuite = any("C-suite" in str(s) for s in active_status)
    has_extra_care = any("Extra care" in str(s) for s in active_status)

    if has_blocker:
        effort = 1.5
    if has_ghosting:
        effort = max(effort, 1.3)
    if has_csuite:
        effort = max(effort, 1.4)
    if has_extra_care:
        effort = max(effort, 1.2)

    # --- LTV ---
    ltv_2yr = arr * ret * growth * 2
    priority = ltv_2yr / effort

    # --- Tier ---
    if priority >= 100000:
        tier = 1
    elif priority >= 50000:
        tier = 2
    elif priority >= 15000:
        tier = 3
    else:
        tier = 4

    # --- Signals ---
    signals = []
    if atd_roas >= 8:
        signals.append("ROAS\u2605")
    elif atd_roas >= 2:
        signals.append("ROAS\u2713")

    if churn_risk_reason or soft_churn or has_churn_risk:
        signals.append("CHURN")

    if days_inactive >= 20:
        signals.append("IDLE")

    if has_blocker:
        signals.append("INT.ERR")

    if bull and "Yes" in str(bull):
        signals.append("LTV UP")

    # Upsell signal
    is_lower_plan = plan in ("Growth", "Lite", "Starter")
    if (is_lower_plan and shopify >= 100000) or upsell_arr > 0:
        signals.append("UPSELL")

    if ws["rev_share"]:
        signals.append("REVSHARE")

    # NEW signal
    is_new = (
        health is None
        and campaigns == 0
        and (tenure_months is None or tenure_months < 2)
    )
    if is_new:
        signals.append("NEW")

    # --- Action/Note ---
    act_parts = []
    if health is None:
        act_parts.append("Rate health.")
    if "CHURN" in signals and health is None:
        act_parts[-1] = "Rate health urgently."
    if churn_risk_reason:
        act_parts.append("Overdue/cancelled.")
    if atd_roas >= 8:
        act_parts.append(f"Strong {atd_roas:.1f}x ROAS." if atd_roas else "")
    elif atd_roas >= 2:
        act_parts.append(f"Good {atd_roas:.2g}x ROAS.")
    if shopify >= 100000:
        act_parts.append(f"${shopify/1000:.0f}K Shopify.")
    if "UPSELL" in signals:
        act_parts.append("Upsell candidate.")
    if ws["comment"]:
        act_parts.append(ws["comment"][:80])

    action = " ".join(act_parts) if act_parts else "Monitor."
    if len(action) > 140:
        action = action[:137] + "..."

    return {
        "arr": arr,
        "ret": round(ret, 2),
        "growth": round(growth, 2),
        "ltv": round(ltv_2yr),
        "priority": round(priority),
        "tier": tier,
        "signals": signals,
        "action": action,
        "start_date": start_date,
        "est_ltv": est_ltv,
        "effort": effort,
    }


# ─── Main Pipeline ──────────────────────────────────────────────────────────────

def load_and_parse():
    """Load all data files and parse records."""
    all_records = {}

    # Parse data files
    for fname, manager_id in DATA_FILES.items():
        path = os.path.join(DATA_DIR, fname)
        with open(path) as f:
            data = json.load(f)
        text = data[0]["text"]
        records = parse_attio_text(text, manager_id)
        for rec in records:
            norm = normalize_record(rec, trust_created_at=False)
            rid = norm["record_id"]
            if rid not in all_records:
                all_records[rid] = norm

    # Add Aimy hardcoded data (created_at is meaningful here)
    for rec in AIMY_DATA:
        norm = normalize_record(rec, trust_created_at=True)
        rid = norm["record_id"]
        if rid not in all_records:
            all_records[rid] = norm

    # Add Hamsa hardcoded data (created_at is meaningful here)
    for rec in HAMSA_DATA:
        norm = normalize_record(rec, trust_created_at=True)
        rid = norm["record_id"]
        if rid not in all_records:
            all_records[rid] = norm

    return list(all_records.values())


def build_workspace_data(workspaces):
    """Compute LTV for all workspaces and return enriched data."""
    results = []
    for ws in workspaces:
        ltv_data = compute_ltv(ws)
        ws.update(ltv_data)
        results.append(ws)

    # Sort by priority descending
    results.sort(key=lambda x: x["priority"], reverse=True)
    return results


def generate_js_data(workspaces):
    """Generate the JavaScript data array string."""
    # Group by pod and sort within each pod
    pods = {}
    for ws in workspaces:
        pod = ws["pod"]
        if pod not in pods:
            pods[pod] = []
        pods[pod].append(ws)

    # Sort each pod by priority descending
    for pod in pods:
        pods[pod].sort(key=lambda x: x["priority"], reverse=True)

    # Build JS entries - one flat array sorted by pod then priority
    js_entries = []
    pod_order = ["Marcus+Martin", "Sebastian+Daniel", "Aimy+Espen", "Nicklas+Hamsa"]

    for pod_name in pod_order:
        pod_ws = pods.get(pod_name, [])
        for rank, ws in enumerate(pod_ws, 1):
            # Escape name for JS
            name_esc = ws["name"].replace("\\", "\\\\").replace("'", "\\'")
            comment_esc = ws["action"].replace("\\", "\\\\").replace("'", "\\'").replace("\r", "").replace("\n", " ")

            sigs_str = ",".join(f'"{s}"' for s in ws["signals"])

            cs_val = ws["est_ltv"]
            cs_js = str(cs_val) if cs_val is not None else "null"

            sd_val = ws["start_date"]
            sd_js = f"'{sd_val}'" if sd_val else "null"

            entry = (
                f"{{r:{rank},n:'{name_esc}',c:'{ws['csm']}',p:'{ws['pod']}',"
                f"pl:'{ws['plan']}',h:{ws['health'] if ws['health'] is not None else 'null'},"
                f"a:{ws['arr']},sh:{round(ws['shopify'])},ro:{ws['roas'] if ws['roas'] else 0},"
                f"ar:{ws['atd_roas'] if ws['atd_roas'] else 0},"
                f"ret:{ws['ret']},g:{ws['growth']},l:{ws['ltv']},pi:{ws['priority']},"
                f"t:{ws['tier']},s:[{sigs_str}],"
                f"cs:{cs_js},sd:{sd_js},"
                f"act:'{comment_esc}',"
                f"w:'{ws['workspace_id']}',ri:'{ws['record_id']}',"
                f"ca:{ws['campaigns']},d:{ws['days_inactive']}}}"
            )
            js_entries.append(entry)

    return "const D=[\n" + ",\n".join(js_entries) + "\n];"


def compute_pod_meta(workspaces):
    """Compute pod-level metadata for PM constant."""
    pods = {}
    for ws in workspaces:
        pod = ws["pod"]
        if pod not in pods:
            pods[pod] = {"workspaces": [], "csms": {}}
        pods[pod]["workspaces"].append(ws)
        csm = ws["csm"]
        if csm not in pods[pod]["csms"]:
            pods[pod]["csms"][csm] = {"workspaces": [], "role": "FE"}
        pods[pod]["csms"][csm]["workspaces"].append(ws)

    # Determine roles from CSM_MAP
    for csm_id, (name, role, pod) in CSM_MAP.items():
        if pod in pods and name in pods[pod]["csms"]:
            pods[pod]["csms"][name]["role"] = role

    pm_entries = []
    pod_order = ["Marcus+Martin", "Sebastian+Daniel", "Aimy+Espen", "Nicklas+Hamsa"]

    total_ws = 0
    total_arr = 0
    total_ltv = 0
    total_risk = 0

    for pod_name in pod_order:
        if pod_name not in pods:
            continue
        pod = pods[pod_name]
        ws_list = pod["workspaces"]
        cnt = len(ws_list)
        arr = sum(w["arr"] for w in ws_list)
        ltv = sum(w["ltv"] for w in ws_list)
        rated = sum(1 for w in ws_list if w["health"] is not None)
        risk = sum(1 for w in ws_list if w["health"] is not None and w["health"] <= 3)
        t1 = sum(1 for w in ws_list if w["tier"] == 1)
        t2 = sum(1 for w in ws_list if w["tier"] == 2)
        t3 = sum(1 for w in ws_list if w["tier"] == 3)
        t4 = sum(1 for w in ws_list if w["tier"] == 4)

        total_ws += cnt
        total_arr += arr
        total_ltv += ltv
        total_risk += risk

        csm_entries = []
        # Sort CSMs: FE first
        csm_items = sorted(pod["csms"].items(), key=lambda x: (0 if x[1]["role"] == "FE" else 1, x[0]))
        for csm_name, csm_data in csm_items:
            c_ws = csm_data["workspaces"]
            c_cnt = len(c_ws)
            c_arr = sum(w["arr"] for w in c_ws)
            c_unr = sum(1 for w in c_ws if w["health"] is None)
            c_role = csm_data["role"]
            c_cl = "blue" if c_role == "FE" else "purple"
            csm_entries.append(
                f"{{n:'{csm_name}',role:'{c_role}',cl:'{c_cl}',cnt:{c_cnt},arr:{c_arr},unr:{c_unr}}}"
            )

        pm_entries.append(
            f"'{pod_name}':{{cnt:{cnt},arr:{arr},ltv:{ltv},rated:{rated},"
            f"risk:{risk},t1:{t1},t2:{t2},t3:{t3},t4:{t4},"
            f"csms:[{','.join(csm_entries)}]}}"
        )

    pm_js = "const PM={" + ",".join(pm_entries) + "};"
    total_js = f"const TOTAL={{ws:{total_ws},arr:{total_arr},ltv:{total_ltv},risk:{total_risk}}};"

    return pm_js, total_js, {
        "ws": total_ws, "arr": total_arr, "ltv": total_ltv, "risk": total_risk,
        "pods": {pn: {"cnt": len(pods[pn]["workspaces"])} for pn in pod_order if pn in pods}
    }


# ─── Daily Churn Data ────────────────────────────────────────────────────────────

def compute_daily_churn(workspaces):
    """Compute yesterday's churn data grouped by pod for the Daily Customer Update."""
    # Build a lookup from record_id -> workspace info
    ws_lookup = {}
    for ws in workspaces:
        ws_lookup[ws["record_id"]] = ws

    pod_order = ["Marcus+Martin", "Sebastian+Daniel", "Aimy+Espen", "Nicklas+Hamsa"]

    # Compute per-pod totals
    pod_totals = {}
    for pod_name in pod_order:
        pod_ws = [w for w in workspaces if w["pod"] == pod_name]
        s3 = sum(1 for w in pod_ws if w.get("est_ltv") == 3)
        s2 = sum(1 for w in pod_ws if w.get("est_ltv") == 2)
        s1 = sum(1 for w in pod_ws if w.get("est_ltv") == 1)
        sna = len(pod_ws) - s3 - s2 - s1
        pod_totals[pod_name] = {
            "count": len(pod_ws),
            "arr": sum(w["arr"] for w in pod_ws),
            "s3": s3, "s2": s2, "s1": s1, "sna": sna,
        }

    # Find churns from yesterday
    pod_churns = {p: [] for p in pod_order}

    for record_id, churn_entries in SUBSCRIPTION_CHURN_DATA.items():
        for entry in churn_entries:
            if entry.get("end_date") == YESTERDAY_STR:
                # Find this workspace's pod
                ws = ws_lookup.get(record_id)
                pod = ws["pod"] if ws else "Unknown"
                name = ws["name"] if ws else "Unknown"
                lost_reason = ws.get("lost_reason", "") if ws else ""
                churn_comment = ws.get("churn_comment", "") if ws else ""
                ctx = CHURN_CONTEXT.get(record_id, {})
                churn_summary = ctx.get("summary", "")
                churn_source = ctx.get("source", "")
                if pod in pod_churns:
                    pod_churns[pod].append({
                        "record_id": record_id,
                        "name": name,
                        "plan": entry.get("plan", "Unknown"),
                        "arr": entry.get("arr", 0),
                        "sub_status": entry.get("sub_status", ""),
                        "stripe_sub_id": entry.get("stripe_sub_id", ""),
                        "lost_reason": lost_reason,
                        "churn_comment": churn_comment,
                        "churn_summary": churn_summary,
                        "churn_source": churn_source,
                    })

    # Build JS constant
    js_parts = []
    for pod_name in pod_order:
        churns = pod_churns[pod_name]
        totals = pod_totals.get(pod_name, {"count": 0, "arr": 0})
        churn_js_items = []
        for c in churns:
            name_esc = c["name"].replace("\\", "\\\\").replace("'", "\\'")
            sub_status_esc = c["sub_status"].replace("\\", "\\\\").replace("'", "\\'")
            lr_esc = c["lost_reason"].replace("\\", "\\\\").replace("'", "\\'")
            cc_esc = c["churn_comment"].replace("\\", "\\\\").replace("'", "\\'")
            cs_esc = c["churn_summary"].replace("\\", "\\\\").replace("'", "\\'")
            csrc = c["churn_source"]
            churn_js_items.append(
                f"{{ri:'{c['record_id']}',n:'{name_esc}',pl:'{c['plan']}',"
                f"arr:{c['arr']},ss:'{sub_status_esc}',sid:'{c['stripe_sub_id']}',"
                f"lr:'{lr_esc}',cc:'{cc_esc}',cs:'{cs_esc}',csrc:'{csrc}'}}"
            )
        churns_str = ",".join(churn_js_items)
        churn_count = len(churns)
        churn_arr = sum(c["arr"] for c in churns)
        js_parts.append(
            f"'{pod_name}':{{cnt:{totals['count']},arr:{totals['arr']},"
            f"s3:{totals['s3']},s2:{totals['s2']},s1:{totals['s1']},sna:{totals['sna']},"
            f"churnCnt:{churn_count},churnArr:{churn_arr},"
            f"churns:[{churns_str}]}}"
        )

    return "const DAILY={" + ",".join(js_parts) + "};"


# ─── Onboarding Queue ────────────────────────────────────────────────────────────

def compute_onboarding_queue(workspaces):
    """Find workspaces with future onboarding dates and compute days since first payment."""
    today_str = TODAY.isoformat()
    queue = []
    seen_ids = set()
    # First pass: workspaces from main data
    for ws in workspaces:
        ob_date = ws.get("onboarding_date")
        if not ob_date or ob_date < today_str:
            continue
        seen_ids.add(ws["record_id"])
        record_id = ws["record_id"]
        start_date = SUBSCRIPTION_START_DATES.get(record_id) or ""
        days_gap = ""
        if start_date and ob_date:
            try:
                sd = date.fromisoformat(start_date)
                od = date.fromisoformat(ob_date)
                days_gap = (od - sd).days
            except ValueError:
                days_gap = ""
        days_until = ""
        try:
            od = date.fromisoformat(ob_date)
            days_until = (od - TODAY).days
        except ValueError:
            pass
        queue.append({
            "record_id": record_id,
            "name": ws["name"],
            "pod": ws["pod"],
            "plan": ws.get("plan", ""),
            "arr": ws.get("arr", 0),
            "mrr": ws.get("mrr", 0),
            "onboarding_date": ob_date,
            "start_date": start_date,
            "days_gap": days_gap,
            "days_until": days_until,
            "last_payment": "",
            "renewal_date": "",
            "billing_cycle": "",
            "sales_rep": "",
        })
    # Add supplemental onboarding records not in main workspace data
    for extra in ONBOARDING_QUEUE_EXTRA:
        if extra["record_id"] in seen_ids:
            continue
        ob_date = extra["onboarding_date"]
        if ob_date < today_str:
            continue
        record_id = extra["record_id"]
        start_date = extra.get("start_date") or SUBSCRIPTION_START_DATES.get(record_id) or ""
        days_gap = ""
        if start_date and ob_date:
            try:
                sd = date.fromisoformat(start_date)
                od = date.fromisoformat(ob_date)
                days_gap = (od - sd).days
            except ValueError:
                days_gap = ""
        days_until = ""
        try:
            od = date.fromisoformat(ob_date)
            days_until = (od - TODAY).days
        except ValueError:
            pass
        queue.append({
            "record_id": record_id,
            "name": extra["name"],
            "pod": extra["pod"],
            "plan": extra.get("plan", ""),
            "arr": extra.get("arr", 0),
            "mrr": extra.get("mrr", 0),
            "onboarding_date": ob_date,
            "start_date": start_date,
            "days_gap": days_gap,
            "days_until": days_until,
            "last_payment": extra.get("last_payment", ""),
            "renewal_date": extra.get("renewal_date", ""),
            "billing_cycle": extra.get("billing_cycle", ""),
            "sales_rep": extra.get("sales_rep", ""),
        })
    # Sort by onboarding date ascending (soonest first)
    queue.sort(key=lambda x: x["onboarding_date"])

    # Build JS array
    js_items = []
    for q in queue:
        n_esc = q["name"].replace("\\", "\\\\").replace("'", "\\'")
        js_items.append(
            f"{{ri:'{q['record_id']}',n:'{n_esc}',pod:'{q['pod']}',"
            f"pl:'{q['plan']}',arr:{q['arr']},mrr:{q.get('mrr', 0)},"
            f"ob:'{q['onboarding_date']}',sd:'{q['start_date']}',"
            f"lp:'{q.get('last_payment', '')}',rd:'{q.get('renewal_date', '')}',"
            f"bc:'{q.get('billing_cycle', '')}',"
            f"sr:'{q.get('sales_rep', '')}',"
            f"gap:{q['days_gap'] if q['days_gap'] != '' else 'null'},"
            f"until:{q['days_until'] if q['days_until'] != '' else 'null'}}}"
        )
    print(f"  Onboarding queue: {len(queue)} upcoming onboardings")
    return "const ONBOARD=[" + ",".join(js_items) + "];"


# ─── HTML Template ──────────────────────────────────────────────────────────────

def generate_html(js_data, pm_js, total_js, daily_js, onboard_js, stats):
    """Generate the complete HTML dashboard."""

    total_ws = stats["ws"]
    total_arr = stats["arr"]
    total_ltv = stats["ltv"]

    def fmt_m(v):
        if v >= 1e6:
            return f"${v/1e6:.1f}M"
        if v >= 1e3:
            return f"${v/1e3:.0f}K"
        return f"${v}"

    pod_counts = stats["pods"]
    mm_cnt = pod_counts.get('Marcus+Martin', {}).get('cnt', 0)
    sd_cnt = pod_counts.get('Sebastian+Daniel', {}).get('cnt', 0)
    ae_cnt = pod_counts.get('Aimy+Espen', {}).get('cnt', 0)
    nh_cnt = pod_counts.get('Nicklas+Hamsa', {}).get('cnt', 0)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CSM Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = {{
  theme: {{
    extend: {{
      colors: {{
        dark: {{ 50:'#f8fafc',100:'#f1f5f9',200:'#e2e8f0',300:'#cbd5e1',400:'#94a3b8',500:'#64748b',600:'#475569',700:'#334155',800:'#1e293b',900:'#0f172a',950:'#020617' }}
      }}
    }}
  }}
}}
</script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  body {{ font-family: 'Inter', sans-serif; }}
  .glass {{ background: rgba(255,255,255,0.03); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.06); }}
  .tier-1-row {{ border-left: 3px solid #22c55e; }}
  .tier-2-row {{ border-left: 3px solid #3b82f6; }}
  .tier-3-row {{ border-left: 3px solid #f59e0b; }}
  .tier-4-row {{ border-left: 3px solid #ef4444; }}
  .signal-tag {{ font-size: 0.65rem; padding: 2px 6px; border-radius: 4px; font-weight: 600; white-space: nowrap; }}
  .scrollbar-thin::-webkit-scrollbar {{ width: 6px; height: 6px; }}
  .scrollbar-thin::-webkit-scrollbar-track {{ background: rgba(255,255,255,0.03); }}
  .scrollbar-thin::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.1); border-radius: 3px; }}
  tr.workspace-row {{ transition: background 0.15s; }}
  tr.workspace-row:hover {{ background: rgba(255,255,255,0.04); }}
  .fade-in {{ animation: fadeIn 0.4s ease-out; }}
  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  .pod-tab {{ cursor:pointer; transition: all 0.2s; }}
  .pod-tab.active {{ background: rgba(255,255,255,0.08); color: #e2e8f0; border-color: rgba(255,255,255,0.15); }}
  .pod-tab:not(.active):hover {{ background: rgba(255,255,255,0.04); }}
  .link-icon {{ opacity: 0.5; transition: opacity 0.15s; }}
  .link-icon:hover {{ opacity: 1; }}
  .tip {{ position: relative; cursor: help; }}
  .tip .tip-text {{ visibility: hidden; opacity: 0; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); margin-top: 8px; padding: 8px 12px; background: #1e293b; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; color: #cbd5e1; font-size: 0.75rem; font-weight: 400; text-transform: none; letter-spacing: 0; line-height: 1.5; white-space: normal; width: 240px; z-index: 50; transition: opacity 0.15s, visibility 0.15s; box-shadow: 0 4px 12px rgba(0,0,0,0.3); pointer-events: none; }}
  .tip:hover .tip-text {{ visibility: visible; opacity: 1; }}
  .tip .tip-text::before {{ content: ''; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); border: 6px solid transparent; border-bottom-color: #1e293b; }}
  th {{ position: relative; white-space: nowrap; }}
  td {{ white-space: nowrap; }}
  th .col-resize {{ position: absolute; right: 0; top: 0; bottom: 0; width: 5px; cursor: col-resize; z-index: 5; }}
  th .col-resize:hover, th .col-resize.active {{ background: rgba(56,189,248,0.4); }}
  th.sortable {{ cursor: pointer; user-select: none; }}
  th.sortable:hover {{ color: #e2e8f0; }}
  .sort-arrow {{ font-size: 0.6rem; margin-left: 2px; opacity: 0.3; }}
  th.sortable.asc .sort-arrow, th.sortable.desc .sort-arrow {{ opacity: 1; color: #38bdf8; }}
  .col-filter {{ display: inline-block; position: relative; }}
  .col-filter-btn {{ font-size: 0.55rem; margin-left: 3px; padding: 1px 3px; border-radius: 3px; opacity: 0.4; cursor: pointer; vertical-align: middle; }}
  .col-filter-btn:hover, .col-filter-btn.active {{ opacity: 1; background: rgba(255,255,255,0.08); }}
  .col-dropdown {{ display: none; position: absolute; top: 100%; left: 0; margin-top: 6px; background: #1e293b; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 6px 0; min-width: 160px; z-index: 60; box-shadow: 0 4px 12px rgba(0,0,0,0.4); max-height: 240px; overflow-y: auto; }}
  .col-dropdown.show {{ display: block; }}
  .col-dropdown label {{ display: flex; align-items: center; gap: 6px; padding: 4px 12px; font-size: 0.75rem; font-weight: 400; text-transform: none; letter-spacing: 0; color: #94a3b8; cursor: pointer; white-space: nowrap; }}
  .col-dropdown label:hover {{ background: rgba(255,255,255,0.05); color: #e2e8f0; }}
  #authGate {{ position: fixed; inset: 0; z-index: 999; background: #020617; display: flex; align-items: center; justify-content: center; }}
  #authGate.hidden {{ display: none; }}
  #dashboard.locked {{ display: none; }}
  .top-tab {{ cursor: pointer; transition: all 0.2s; padding: 10px 24px; font-size: 0.875rem; font-weight: 600; border-bottom: 2px solid transparent; color: #64748b; }}
  .top-tab.active {{ color: #e2e8f0; border-bottom-color: #38bdf8; }}
  .top-tab:not(.active):hover {{ color: #94a3b8; }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  .churn-accordion {{ cursor: pointer; user-select: none; }}
  .churn-accordion .chevron {{ transition: transform 0.2s; display: inline-block; }}
  .churn-accordion.open .chevron {{ transform: rotate(90deg); }}
  .churn-detail {{ display: none; }}
  .churn-detail.open {{ display: block; }}
</style>
</head>
<body class="bg-dark-950 text-dark-200 min-h-screen">

<!-- Password Gate -->
<div id="authGate">
  <div class="text-center px-6">
    <p class="text-dark-400 text-sm font-medium uppercase tracking-wider mb-2">CSM Dashboard</p>
    <h1 class="text-2xl font-800 text-white mb-6">Enter password to continue</h1>
    <form onsubmit="return checkPw()" class="flex flex-col items-center gap-3">
      <input type="password" id="pwInput" placeholder="Password" autofocus class="px-4 py-3 rounded-lg text-sm bg-dark-800/50 text-dark-200 border border-dark-700 focus:border-dark-500 focus:outline-none w-64 text-center" />
      <button type="submit" class="px-6 py-2.5 rounded-lg text-sm font-600 bg-white/10 text-white border border-white/10 hover:bg-white/15 transition w-64">Enter</button>
      <p id="pwError" class="text-red-400 text-xs hidden">Incorrect password</p>
    </form>
  </div>
</div>

<div id="dashboard" class="locked max-w-[1500px] mx-auto px-4 sm:px-6 py-8">

  <!-- Page Header -->
  <div class="fade-in mb-2">
    <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-2">
      <div>
        <p class="text-dark-400 text-sm font-medium uppercase tracking-wider mb-1">CSM Dashboard</p>
      </div>
      <div class="text-right">
        <p class="text-dark-500 text-sm">Updated Feb 17, 2026</p>
      </div>
    </div>
  </div>

  <!-- Top-level Tab Bar -->
  <div class="flex border-b border-dark-800 mb-6 fade-in">
    <button class="top-tab active" data-toptab="daily" onclick="switchTopTab('daily')">Daily Customer Update</button>
    <button class="top-tab" data-toptab="priority" onclick="switchTopTab('priority')">Customer Prioritization</button>
    <button class="top-tab" data-toptab="onboard" onclick="switchTopTab('onboard')">Onboarding Queue</button>
  </div>

  <!-- ============ DAILY CUSTOMER UPDATE TAB ============ -->
  <div id="tabDaily" class="tab-panel active fade-in">
    <div class="mb-6">
      <div class="flex items-center gap-4 mb-1">
        <h1 class="text-3xl sm:text-4xl font-800 text-white">Daily Customer Update</h1>
        <button onclick="document.getElementById('infoDailyPage').classList.toggle('hidden')" class="shrink-0 px-4 py-2 rounded-lg text-sm font-600 bg-dark-800/50 text-dark-400 border border-dark-700/50 hover:bg-dark-700 hover:text-dark-200 transition">How This Works</button>
      </div>
      <p class="text-dark-400 text-sm">Feb 17, 2026 &mdash; Yesterday's churn summary across all pods</p>
    </div>

    <!-- Daily Info Page (hidden by default) -->
    <div id="infoDailyPage" class="hidden glass rounded-xl p-6 sm:p-8 mb-6 fade-in">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-800 text-white">How This Page Works</h2>
        <button onclick="document.getElementById('infoDailyPage').classList.add('hidden')" class="text-dark-400 hover:text-white text-xl px-2">&times;</button>
      </div>
      <div class="space-y-5 text-sm">
        <div>
          <h3 class="text-base font-700 text-white mb-2">What is this page?</h3>
          <p class="text-dark-300 leading-relaxed">A daily snapshot of customer churn across all 4 CSM pods. It shows how many customers and how much ARR each pod lost yesterday, so leadership can spot problems quickly and follow up same-day.</p>
        </div>
        <div>
          <h3 class="text-base font-700 text-white mb-2">How pods are ranked</h3>
          <p class="text-dark-300 leading-relaxed">Pods are ranked best-to-worst each day using two simple rules:</p>
          <ol class="text-dark-300 leading-relaxed list-decimal list-inside mt-2 space-y-1">
            <li><strong class="text-white">Least MRR churned</strong> &mdash; the pod that lost the least revenue ranks highest.</li>
            <li><strong class="text-white">Most ARR under management</strong> &mdash; if two pods tied on churn, the one managing more total ARR ranks higher.</li>
          </ol>
        </div>
        <div>
          <h3 class="text-base font-700 text-white mb-2">Medals</h3>
          <p class="text-dark-300 leading-relaxed">The top 3 pods receive gold, silver, and bronze medals. This resets every day &mdash; yesterday's winner starts fresh today.</p>
        </div>
        <div>
          <h3 class="text-base font-700 text-white mb-2">Churn details</h3>
          <p class="text-dark-300 leading-relaxed">Click the churn row on any pod card to expand and see which customers cancelled, their plan, lost ARR, cancellation reason from Stripe, and direct links to Stripe and Attio.</p>
        </div>
      </div>
    </div>

    <div class="glass rounded-xl p-5 mb-6" id="dailyAggregate"></div>
    <div class="grid grid-cols-1 gap-4" id="dailyCards"></div>
  </div>

  <!-- ============ CUSTOMER PRIORITIZATION TAB ============ -->
  <div id="tabPriority" class="tab-panel fade-in">

  <!-- Priority Header -->
  <div class="mb-6">
    <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-2">
      <div class="flex items-center gap-4">
        <h1 class="text-3xl sm:text-4xl font-800 text-white">All Pods Overview</h1>
        <button onclick="document.getElementById('infoPage').classList.toggle('hidden')" class="shrink-0 px-4 py-2 rounded-lg text-sm font-600 bg-dark-800/50 text-dark-400 border border-dark-700/50 hover:bg-dark-700 hover:text-dark-200 transition">How This Works</button>
      </div>
      <div class="text-right">
        <p class="text-dark-600 text-xs">{total_ws} workspaces &middot; {fmt_m(total_arr)} ARR &middot; {fmt_m(total_ltv)} est. 2yr LTV</p>
      </div>
    </div>
    <p class="text-dark-400 text-sm max-w-3xl">LTV-based priority model for CSM resource allocation across all pods. Workspaces ranked by estimated 2-year lifetime value adjusted for retention probability, growth potential, and required CSM effort.</p>
  </div>

  <!-- Info Page (hidden by default) -->
  <div id="infoPage" class="hidden glass rounded-xl p-6 sm:p-8 mb-8 fade-in">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-800 text-white">How This Dashboard Works</h2>
      <button onclick="document.getElementById('infoPage').classList.add('hidden')" class="text-dark-400 hover:text-white text-xl px-2">&times;</button>
    </div>

    <div class="space-y-8 text-sm">

      <!-- What is this? -->
      <div>
        <h3 class="text-base font-700 text-white mb-2">What is this dashboard?</h3>
        <p class="text-dark-300 leading-relaxed">This dashboard helps CSM (Customer Success Manager) team leads decide <strong class="text-white">where to spend their team's time</strong>. We manage ~{total_ws} client workspaces across 4 pods. Each pod is a pair of CSMs: one &ldquo;front-end&rdquo; (client-facing, runs meetings) and one &ldquo;back-end&rdquo; (operations, campaign setup, creatives). Not every client deserves equal attention &mdash; this tool ranks them by how much long-term value they represent, so CSMs focus on the clients that matter most.</p>
      </div>

      <!-- The big idea -->
      <div>
        <h3 class="text-base font-700 text-white mb-2">The big idea: Priority = Lifetime Value &divide; Effort</h3>
        <p class="text-dark-300 leading-relaxed mb-3">Every workspace gets a <strong class="text-white">Priority Index</strong> score. This is simply: <em>how much is this client worth to us over the next 2 years, divided by how much CSM time they need?</em> High-value, low-effort clients rank highest. At-risk clients that need heavy investment rank lower &mdash; unless saving them protects a lot of revenue.</p>
        <p class="text-dark-300 leading-relaxed">Workspaces are grouped into 4 tiers based on this score:</p>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
          <div class="rounded-lg p-3 border-l-3 border-emerald-500 bg-emerald-500/5">
            <p class="text-emerald-400 font-700">Tier 1</p>
            <p class="text-dark-400 text-xs mt-1">Highest impact. Protect and grow these at all costs.</p>
          </div>
          <div class="rounded-lg p-3 border-l-3 border-blue-500 bg-blue-500/5">
            <p class="text-blue-400 font-700">Tier 2</p>
            <p class="text-dark-400 text-xs mt-1">Important. Steady attention, look for upsell opportunities.</p>
          </div>
          <div class="rounded-lg p-3 border-l-3 border-amber-500 bg-amber-500/5">
            <p class="text-amber-400 font-700">Tier 3</p>
            <p class="text-dark-400 text-xs mt-1">Moderate value. Maintain, but don't over-invest unless a clear signal appears.</p>
          </div>
          <div class="rounded-lg p-3 border-l-3 border-red-500 bg-red-500/5">
            <p class="text-red-400 font-700">Tier 4</p>
            <p class="text-dark-400 text-xs mt-1">Low priority. Minimal effort. Consider offboarding if failing.</p>
          </div>
        </div>
      </div>

      <!-- How LTV is calculated -->
      <div>
        <h3 class="text-base font-700 text-white mb-2">How we estimate 2-Year Lifetime Value</h3>
        <p class="text-dark-300 leading-relaxed mb-3">The formula: <code class="bg-dark-800 px-2 py-0.5 rounded text-emerald-400">2yr LTV = Annual Revenue &times; Retention Chance &times; Growth Potential &times; 2</code></p>
        <div class="space-y-3">
          <div class="flex gap-3">
            <span class="text-white font-600 shrink-0 w-36">Annual Revenue</span>
            <p class="text-dark-400">Estimated from the client's plan level (e.g. Pro &asymp; $25K/yr, Performance &asymp; $48K/yr). This is an average, not the exact subscription price.</p>
          </div>
          <div class="flex gap-3">
            <span class="text-white font-600 shrink-0 w-36">Retention Chance</span>
            <p class="text-dark-400">How likely the client is to stay. Based on their health rating: a 5-star client has a 92% chance of renewing, a 1-star client only 25%. Clients with overdue invoices or long periods of inactivity get further penalties. Longer-tenured clients get a small boost (up to 1.2x for 18+ months) since they have proven commitment. Unrated clients default to 65%.</p>
          </div>
          <div class="flex gap-3">
            <span class="text-white font-600 shrink-0 w-36">Growth Potential</span>
            <p class="text-dark-400">A multiplier (0.5x to 3.5x) based on how much room there is to grow. Clients with strong ROAS (good ad returns), large Shopify stores, or CSM-flagged &ldquo;Time=ROAS&rdquo; potential score higher. The <strong class="text-dark-200">Customer Score</strong> (est_ltv field) further adjusts growth: Score 3 gets a 1.4x boost, Score 2 gets 1.15x. Clients with zero campaigns and no data score lower.</p>
          </div>
        </div>
      </div>

      <!-- What the columns mean -->
      <div>
        <h3 class="text-base font-700 text-white mb-2">Column guide</h3>
        <p class="text-dark-400 mb-3">Hover any column header in the table for a quick explanation. Here's the full breakdown:</p>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div class="bg-dark-800/30 rounded-lg p-3">
            <p class="text-white font-600">Health (1-5 stars)</p>
            <p class="text-dark-400 text-xs mt-1">The CSM's gut-check rating of the client relationship. 5 = happy client, strong results. 3 = needs work. 1 = about to leave. &ldquo;Not rated&rdquo; means the CSM hasn't assessed this client yet &mdash; a blind spot.</p>
          </div>
          <div class="bg-dark-800/30 rounded-lg p-3">
            <p class="text-white font-600">Customer Score (1-3)</p>
            <p class="text-dark-400 text-xs mt-1">The CSM's subjective assessment of customer potential and strategic value. Score 3 = high growth/strategic potential (gets a 1.4x growth boost in LTV). Score 2 = moderate potential (1.15x boost). Score 1 = standard. This field directly influences how much growth upside the model assigns to a client.</p>
          </div>
          <div class="bg-dark-800/30 rounded-lg p-3">
            <p class="text-white font-600">Start Date</p>
            <p class="text-dark-400 text-xs mt-1">Subscription start date from Stripe (date of first payment). Longer tenure means more confidence in retention &mdash; clients who have been with us 18+ months get up to a 1.2x retention boost. New clients (&lt;1 month) get a 0.9x penalty since they haven't proven commitment yet.</p>
          </div>
          <div class="bg-dark-800/30 rounded-lg p-3">
            <p class="text-white font-600">ROAS (ATD)</p>
            <p class="text-dark-400 text-xs mt-1">All-Time-Data Return on Ad Spend. If a client spent $1,000 on ads through us and earned $5,000 in sales, their ROAS is 5.0x. Higher is better. This is the lifetime average, not just the last month.</p>
          </div>
          <div class="bg-dark-800/30 rounded-lg p-3">
            <p class="text-white font-600">Shopify/30d</p>
            <p class="text-dark-400 text-xs mt-1">Total sales through the client's Shopify store in the last 30 days. Tells us how big their business is. A client doing $500K/mo in sales has much more upside than one doing $2K/mo.</p>
          </div>
          <div class="bg-dark-800/30 rounded-lg p-3">
            <p class="text-white font-600">Ret. %</p>
            <p class="text-dark-400 text-xs mt-1">How likely this customer is to stay for another year. Based on health rating, churn signals, activity level, and how long they've been a customer. Higher = more likely to renew. A client with 92% retention is worth almost 4x more over 2 years than one at 25%.</p>
          </div>
          <div class="bg-dark-800/30 rounded-lg p-3">
            <p class="text-white font-600">2yr LTV</p>
            <p class="text-dark-400 text-xs mt-1">The estimated total revenue from this client over 2 years. This is the single most important number. It factors in their plan price, how likely they are to stay, and how much they could grow.</p>
          </div>
          <div class="bg-dark-800/30 rounded-lg p-3">
            <p class="text-white font-600">Est. ARR</p>
            <p class="text-dark-400 text-xs mt-1">Estimated Annual Recurring Revenue. What we expect this client to pay per year based on their plan tier. Enterprise &asymp; $50K, Performance &asymp; $48K, Pro &asymp; $25K, Growth &asymp; $9K, Lite &asymp; $6K.</p>
          </div>
        </div>
      </div>

      <!-- Signals -->
      <div>
        <h3 class="text-base font-700 text-white mb-2">Signal tags explained</h3>
        <p class="text-dark-400 mb-3">Quick-glance labels that flag important things about a client:</p>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3">
          <div class="flex gap-3 items-start"><span class="signal-tag bg-red-500/10 text-red-400 shrink-0">CHURN</span><p class="text-dark-400">Client is at risk of leaving. Their subscription is cancelled or overdue, or they've been explicitly flagged as a churn risk.</p></div>
          <div class="flex gap-3 items-start"><span class="signal-tag bg-amber-500/10 text-amber-400 shrink-0">IDLE</span><p class="text-dark-400">No active ad campaigns for 20+ days. If a client isn't running ads, they're not seeing value from our service &mdash; churn risk increases.</p></div>
          <div class="flex gap-3 items-start"><span class="signal-tag bg-orange-500/10 text-orange-400 shrink-0">INT.ERR</span><p class="text-dark-400">A technical integration with the client's store is broken. Until this is fixed, we can't deliver value. Needs engineering attention.</p></div>
          <div class="flex gap-3 items-start"><span class="signal-tag bg-emerald-500/10 text-emerald-400 shrink-0">ROAS&#9733;</span><p class="text-dark-400">Excellent all-time ROAS (8x+). This client's ads are performing very well. A star performer worth protecting.</p></div>
          <div class="flex gap-3 items-start"><span class="signal-tag bg-blue-500/10 text-blue-400 shrink-0">ROAS&#10003;</span><p class="text-dark-400">Good all-time ROAS (2x-8x). Ads are working, client should be seeing value. Solid performer.</p></div>
          <div class="flex gap-3 items-start"><span class="signal-tag bg-emerald-500/10 text-emerald-400 shrink-0">LTV UP</span><p class="text-dark-400">The CSM believes this client has untapped potential. Given more time and attention, the return could be significant. Prioritize.</p></div>
          <div class="flex gap-3 items-start"><span class="signal-tag bg-cyan-500/10 text-cyan-400 shrink-0">UPSELL</span><p class="text-dark-400">Client's usage or business size suggests they should be on a higher plan. E.g. a $500K/mo Shopify store on a $9K Growth plan.</p></div>
          <div class="flex gap-3 items-start"><span class="signal-tag bg-teal-500/10 text-teal-400 shrink-0">REVSHARE</span><p class="text-dark-400">We have a revenue-share agreement with this client &mdash; we earn a % of their ad-driven revenue. Aligned incentives: the better they do, the more we earn.</p></div>
          <div class="flex gap-3 items-start"><span class="signal-tag bg-dark-700 text-dark-300 shrink-0">NEW</span><p class="text-dark-400">New client still in onboarding or with very limited data. Too early to judge performance &mdash; needs time to ramp up.</p></div>
        </div>
      </div>

      <!-- Pod structure -->
      <div>
        <h3 class="text-base font-700 text-white mb-2">Pod structure</h3>
        <p class="text-dark-300 leading-relaxed mb-3">The CSM team is organized into 4 pods. Each pod has two people:</p>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="bg-dark-800/30 rounded-lg p-3">
            <p class="text-white font-600">Front-End CSM (FE)</p>
            <p class="text-dark-400 text-xs mt-1">The team lead. Client-facing: runs meetings, manages the relationship, handles escalations. The face the client sees.</p>
          </div>
          <div class="bg-dark-800/30 rounded-lg p-3">
            <p class="text-white font-600">Back-End CSM (BE)</p>
            <p class="text-dark-400 text-xs mt-1">Operations: sets up campaigns, manages creatives, handles technical setup. Does the behind-the-scenes work that delivers results.</p>
          </div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-center">
          <div class="bg-dark-800/30 rounded-lg p-3"><p class="text-blue-400 font-600 text-xs">Marcus (FE)</p><p class="text-purple-400 font-600 text-xs">Martin (BE)</p><p class="text-dark-500 text-xs mt-1">{mm_cnt} workspaces</p></div>
          <div class="bg-dark-800/30 rounded-lg p-3"><p class="text-blue-400 font-600 text-xs">Sebastian (FE)</p><p class="text-purple-400 font-600 text-xs">Daniel (BE)</p><p class="text-dark-500 text-xs mt-1">{sd_cnt} workspaces</p></div>
          <div class="bg-dark-800/30 rounded-lg p-3"><p class="text-blue-400 font-600 text-xs">Aimy (FE)</p><p class="text-purple-400 font-600 text-xs">Espen (BE)</p><p class="text-dark-500 text-xs mt-1">{ae_cnt} workspaces</p></div>
          <div class="bg-dark-800/30 rounded-lg p-3"><p class="text-blue-400 font-600 text-xs">Nicklas (FE)</p><p class="text-purple-400 font-600 text-xs">Hamsa (BE)</p><p class="text-dark-500 text-xs mt-1">{nh_cnt} workspaces</p></div>
        </div>
      </div>

      <!-- Important caveats -->
      <div>
        <h3 class="text-base font-700 text-white mb-2">Important caveats</h3>
        <ul class="text-dark-400 space-y-2 list-disc list-inside">
          <li><strong class="text-dark-300">ARR is estimated, not exact.</strong> We use plan-level averages, not actual subscription amounts. Individual pricing deals may differ.</li>
          <li><strong class="text-dark-300">Unrated clients are a blind spot.</strong> Workspaces without a health rating default to 65% retention &mdash; this may overstate weak clients or understate strong ones. Rating all clients is the single highest-impact action any CSM can take.</li>
          <li><strong class="text-dark-300">Shopify sales are a 30-day snapshot.</strong> Seasonal businesses may look artificially high or low depending on the time of year.</li>
          <li><strong class="text-dark-300">Customer Score is subjective.</strong> The est_ltv field (Customer Score 1-3) reflects the CSM's own assessment of potential. It directly influences the growth multiplier in the LTV model. Keeping this up to date helps the model surface the right priorities.</li>
          <li><strong class="text-dark-300">The model is directional, not exact.</strong> Use it to guide priorities and spot patterns, not as the final word. CSM judgment and context always matter.</li>
          <li><strong class="text-dark-300">Data comes from Attio CRM.</strong> If CRM records are out of date, the dashboard will reflect stale information. Keep Attio up to date.</li>
        </ul>
      </div>

    </div>
  </div>

  <!-- Pod Tabs -->
  <div class="flex flex-wrap gap-2 mb-6 fade-in" style="animation-delay:0.05s" id="podTabs">
    <button onclick="selectPod('all')" class="pod-tab active px-4 py-2 rounded-lg text-sm font-600 bg-dark-800/50 text-dark-400 border border-dark-700/50" data-pod="all">All Pods ({total_ws})</button>
    <button onclick="selectPod('Marcus+Martin')" class="pod-tab px-4 py-2 rounded-lg text-sm font-600 bg-dark-800/30 text-dark-500 border border-dark-800/30" data-pod="Marcus+Martin">Angus <span class="text-dark-600 text-xs">(Marcus &amp; Martin)</span> ({mm_cnt})</button>
    <button onclick="selectPod('Sebastian+Daniel')" class="pod-tab px-4 py-2 rounded-lg text-sm font-600 bg-dark-800/30 text-dark-500 border border-dark-800/30" data-pod="Sebastian+Daniel">Belgian Blue <span class="text-dark-600 text-xs">(Sebastian &amp; Daniel)</span> ({sd_cnt})</button>
    <button onclick="selectPod('Aimy+Espen')" class="pod-tab px-4 py-2 rounded-lg text-sm font-600 bg-dark-800/30 text-dark-500 border border-dark-800/30" data-pod="Aimy+Espen">Charolais <span class="text-dark-600 text-xs">(Aimy &amp; Espen)</span> ({ae_cnt})</button>
    <button onclick="selectPod('Nicklas+Hamsa')" class="pod-tab px-4 py-2 rounded-lg text-sm font-600 bg-dark-800/30 text-dark-500 border border-dark-800/30" data-pod="Nicklas+Hamsa">Buffalo <span class="text-dark-600 text-xs">(Nicklas &amp; Hamsa)</span> ({nh_cnt})</button>
  </div>

  <!-- KPI Cards (dynamic) -->
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6 fade-in" style="animation-delay:0.1s" id="kpiCards"></div>

  <!-- CSM Split Cards (dynamic) -->
  <div id="csmSplit" class="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4 mb-6 fade-in" style="animation-delay:0.15s"></div>

  <!-- Filter/controls -->
  <div class="flex flex-col sm:flex-row gap-3 mb-4 fade-in" style="animation-delay:0.2s">
    <div class="flex gap-2 flex-wrap" id="tierFilters"></div>
    <div class="flex gap-2 flex-wrap" id="csmFilters"></div>
    <div class="sm:ml-auto">
      <input type="text" id="searchInput" placeholder="Search workspace..." oninput="applyFilters()" class="px-3 py-1.5 rounded-lg text-xs bg-dark-800/50 text-dark-200 border border-dark-700 focus:border-dark-500 focus:outline-none w-48" />
    </div>
  </div>

  <!-- Main Table -->
  <div class="glass rounded-xl overflow-hidden fade-in" style="animation-delay:0.25s">
    <div class="flex items-center justify-end px-4 pt-3 pb-1">
      <span class="text-dark-500 text-xs" id="scrollHint">Scroll right for more columns &rarr;</span>
    </div>
    <div class="overflow-x-auto scrollbar-thin" id="tableScroll">
      <table class="text-sm" id="mainTable">
        <thead>
          <tr class="text-dark-400 text-xs uppercase tracking-wider border-b border-dark-800" id="headerRow">
            <th class="sortable text-left px-3 py-3 font-600" data-sort="pi" data-dir="desc" data-sortable="1"><span class="tip">#<span class="tip-text">Priority rank. #1 = highest-value workspace. Click to sort.</span></span><span class="sort-arrow">&#9660;</span></th>
            <th class="sortable text-left px-3 py-3 font-600" data-sort="n" data-sortable="1"><span class="tip">Workspace<span class="tip-text">The client's workspace name. Click to sort A-Z.</span></span><span class="sort-arrow">&#9650;</span></th>
            <th class="text-left px-3 py-3 font-600"><span class="tip">Pod<span class="tip-text">Which CSM pod manages this client.</span></span><span class="col-filter"><span class="col-filter-btn" onclick="toggleDrop(event,'dropPod')">&#9662;</span><div class="col-dropdown" id="dropPod"></div></span></th>
            <th class="text-left px-3 py-3 font-600"><span class="tip">CSM<span class="tip-text">The Customer Success Manager responsible.</span></span><span class="col-filter"><span class="col-filter-btn" onclick="toggleDrop(event,'dropCSM')">&#9662;</span><div class="col-dropdown" id="dropCSM"></div></span></th>
            <th class="sortable text-left px-3 py-3 font-600" data-sort="sd" data-sortable="1"><span class="tip">Start<span class="tip-text">Subscription start date from Stripe. Longer tenure = more LTV confidence.</span></span><span class="sort-arrow">&#9650;</span></th>
            <th class="text-left px-3 py-3 font-600"><span class="tip">Plan<span class="tip-text">Subscription plan: Starter to Enterprise.</span></span><span class="col-filter"><span class="col-filter-btn" onclick="toggleDrop(event,'dropPlan')">&#9662;</span><div class="col-dropdown" id="dropPlan"></div></span></th>
            <th class="sortable text-center px-3 py-3 font-600" data-sort="h" data-sortable="1"><span class="tip">Health<span class="tip-text">CSM's 1-5 star rating. Click to sort.</span></span><span class="sort-arrow">&#9650;</span><span class="col-filter"><span class="col-filter-btn" onclick="toggleDrop(event,'dropHealth');event.stopPropagation()">&#9662;</span><div class="col-dropdown" id="dropHealth"></div></span></th>
            <th class="sortable text-center px-3 py-3 font-600" data-sort="cs" data-sortable="1"><span class="tip">CS<span class="tip-text">Overall score based on CSM judgement of long-term value. 3 = high growth/strategic potential. 2 = moderate. 1 = low.</span></span><span class="sort-arrow">&#9650;</span><span class="col-filter"><span class="col-filter-btn" onclick="toggleDrop(event,'dropCS');event.stopPropagation()">&#9662;</span><div class="col-dropdown" id="dropCS"></div></span></th>
            <th class="sortable text-right px-3 py-3 font-600" data-sort="a" data-sortable="1"><span class="tip">Est. ARR<span class="tip-text">Estimated annual revenue from plan averages. Click to sort.</span></span><span class="sort-arrow">&#9650;</span></th>
            <th class="sortable text-right px-3 py-3 font-600 desc" data-sort="l" data-sortable="1"><span class="tip">2yr LTV<span class="tip-text">Estimated 2-year lifetime value. Click to sort.</span></span><span class="sort-arrow">&#9660;</span></th>
            <th class="sortable text-right px-3 py-3 font-600" data-sort="sh" data-sortable="1"><span class="tip">Shopify/30d<span class="tip-text">Client's Shopify store sales last 30 days. Click to sort.</span></span><span class="sort-arrow">&#9650;</span></th>
            <th class="sortable text-right px-3 py-3 font-600" data-sort="ar" data-sortable="1"><span class="tip">ROAS (ATD)<span class="tip-text">All-time return on ad spend. Click to sort.</span></span><span class="sort-arrow">&#9650;</span></th>
            <th class="sortable text-center px-3 py-3 font-600" data-sort="ret" data-sortable="1"><span class="tip">Ret. %<span class="tip-text">How likely this customer is to stay for another year. Based on health rating, churn signals, activity level, and tenure. Higher = more likely to renew. Click to sort.</span></span><span class="sort-arrow">&#9650;</span></th>
            <th class="text-left px-3 py-3 font-600"><span class="tip">Signals<span class="tip-text">Quick-glance tags. Use filter to find specific signals.</span></span><span class="col-filter"><span class="col-filter-btn" onclick="toggleDrop(event,'dropSig')">&#9662;</span><div class="col-dropdown" id="dropSig"></div></span></th>
            <th class="text-left px-3 py-3 font-600"><span class="tip">Action / Note<span class="tip-text">Recommended next step or CSM's latest note.</span></span></th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
  </div>


  <p class="text-dark-600 text-xs text-center mt-8 mb-4">Data sourced from Attio CRM. Dashboard generated Feb 2026.</p>

  </div><!-- /tabPriority -->

  <!-- ============ ONBOARDING QUEUE TAB ============ -->
  <div id="tabOnboard" class="tab-panel fade-in">
    <div class="mb-6">
      <h1 class="text-3xl sm:text-4xl font-800 text-white mb-1">Onboarding Queue</h1>
      <p class="text-dark-400 text-sm">Upcoming onboardings &mdash; sorted by date, soonest first</p>
    </div>
    <div id="onboardList"></div>
  </div>

</div>

<script>
{js_data}
{pm_js}
{total_js}
{daily_js}
{onboard_js}

let curPod='all',curTier='all',curCSM='all';
let curTopTab='daily';

function switchTopTab(tab){{
  curTopTab=tab;
  document.querySelectorAll('.top-tab').forEach(b=>{{
    b.classList.toggle('active',b.dataset.toptab===tab);
  }});
  document.getElementById('tabDaily').classList.toggle('active',tab==='daily');
  document.getElementById('tabPriority').classList.toggle('active',tab==='priority');
  document.getElementById('tabOnboard').classList.toggle('active',tab==='onboard');
  if(tab==='priority'){{selectPod(curPod);initColResize();}}
  if(tab==='daily')renderDailyCards();
  if(tab==='onboard')renderOnboard();
}}

function renderDailyCards(){{
  const el=document.getElementById('dailyCards');
  const pods=['Marcus+Martin','Sebastian+Daniel','Aimy+Espen','Nicklas+Hamsa'];
  let totCnt=0,totArr=0,totChurnCnt=0,totChurnArr=0,totS3=0,totS2=0,totS1=0,totSna=0;
  pods.forEach(p=>{{const d=DAILY[p];totCnt+=d.cnt;totArr+=d.arr;totChurnCnt+=d.churnCnt;totChurnArr+=d.churnArr;totS3+=d.s3;totS2+=d.s2;totS1+=d.s1;totSna+=d.sna;}});
  const agEl=document.getElementById('dailyAggregate');
  const agChurnColor=totChurnCnt>0?'text-red-400':'text-emerald-400';
  agEl.innerHTML=`
    <h3 class="text-lg font-700 text-white mb-3">All Teams</h3>
    <div class="grid grid-cols-4 gap-3 text-center">
      <div><p class="text-2xl font-700 text-white">${{totCnt}}</p><p class="text-dark-500 text-xs">Total Customers</p><p class="text-dark-500 text-xs mt-1"><span class="text-amber-400">&#9733;${{totS3}}</span> <span class="text-dark-300">&#9733;${{totS2}}</span> <span class="text-dark-500">&#9733;${{totS1}}</span> <span class="text-dark-600">${{totSna}} n/a</span></p></div>
      <div><p class="text-2xl font-700 text-white">${{fmt(totArr)}}</p><p class="text-dark-500 text-xs">Total ARR</p></div>
      <div><p class="text-2xl font-700 ${{agChurnColor}}">${{totChurnCnt>0?totChurnCnt+' ('+fmtChurnArr(totChurnArr)+')':'0'}}</p><p class="text-dark-500 text-xs">Churned Yesterday</p></div>
      <div><p class="text-2xl font-700 ${{agChurnColor}}">${{((totChurnArr/(totArr+totChurnArr))*100).toFixed(2)}}%</p><p class="text-dark-500 text-xs">Churn Rate</p></div>
    </div>`;
  const podOrder=pods.sort((a,b)=>{{
    const da=DAILY[a],db=DAILY[b];
    if(da.churnArr!==db.churnArr)return da.churnArr-db.churnArr;
    return db.arr-da.arr;
  }});
  const medals=['🥇','🥈','🥉',''];
  el.innerHTML=podOrder.map((pod,idx)=>{{
    const d=DAILY[pod];
    const medal=medals[idx]||'';
    const rank=idx+1;
    const hasCh=d.churnCnt>0;
    const churnColor=hasCh?'text-red-400':'text-emerald-400';
    const churnLabel=hasCh?d.churnCnt+' churned ('+fmtChurnArr(d.churnArr)+')':'No churns yesterday';
    const accordionId='churn_'+pod.replace('+','_');
    let churnRows='';
    if(hasCh){{
      churnRows=d.churns.map(c=>`
        <div class="py-3 border-b border-dark-800/50 last:border-0">
          <div class="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
            <div class="flex-1 min-w-0">
              <p class="text-white text-sm font-600 truncate">${{c.n}}</p>
              <p class="text-dark-500 text-xs mt-0.5">${{c.ss}}</p>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <span class="text-xs text-dark-400">${{c.pl}}</span>
              <span class="text-sm font-600 text-red-400">&minus;${{c.arr.toLocaleString()}}</span>
              <span class="inline-flex gap-2">
                ${{c.sid?'<a href="https://dashboard.stripe.com/subscriptions/'+c.sid+'" target="_blank" rel="noopener" class="text-blue-400/70 hover:text-blue-300 text-xs font-500 underline decoration-blue-400/30 hover:decoration-blue-300/60 transition-colors">Stripe</a>':''}}
                <a href="https://app.attio.com/metric/workspaces/record/${{c.ri}}/overview" target="_blank" rel="noopener" class="text-purple-400/70 hover:text-purple-300 text-xs font-500 underline decoration-purple-400/30 hover:decoration-purple-300/60 transition-colors">Attio</a>
              </span>
            </div>
          </div>
          ${{c.cs?'<p class="text-xs mt-2 px-2 py-1.5 rounded bg-dark-800/50 border border-dark-700/30"><span class="text-dark-400">'+({{'call':'&#128222;','email':'&#9993;','csm_field':'&#128221;'}}[c.csrc]||'&#8226;')+' </span><span class="text-dark-200">'+c.cs+'</span> <span class="text-dark-600 ml-1">via '+c.csrc.replace('_',' ')+'</span></p>':''}}
          ${{c.lr?'<p class="text-xs mt-1.5"><span class="text-dark-500">Churn reason:</span> <span class="text-amber-400 font-500">'+c.lr+'</span></p>':''}}
          ${{c.cc?'<p class="text-xs mt-1 text-dark-400"><span class="text-dark-500">Comment:</span> '+c.cc+'</p>':''}}
        </div>`).join('');
    }}
    return`
    <div class="glass rounded-xl p-5">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <span class="text-dark-500 text-sm font-600">#${{rank}}</span>
          ${{medal?'<span class="text-2xl">'+medal+'</span>':''}}
          <div>
            <h3 class="text-lg font-700 text-white">${{POD_DISPLAY[pod]||pod}}</h3>
            <p class="text-dark-500 text-xs">${{POD_MEMBERS[pod]||pod.replace('+',' + ')}}</p>
          </div>
        </div>
      </div>
      <div class="grid grid-cols-4 gap-3 text-center mb-4">
        <div><p class="text-lg font-700 text-white">${{d.cnt}}</p><p class="text-dark-500 text-xs">Active Customers</p><p class="text-dark-500 text-xs mt-1"><span class="text-amber-400">&#9733;${{d.s3}}</span> <span class="text-dark-300">&#9733;${{d.s2}}</span> <span class="text-dark-500">&#9733;${{d.s1}}</span> <span class="text-dark-600">${{d.sna}} n/a</span></p></div>
        <div><p class="text-lg font-700 text-white">${{fmt(d.arr)}}</p><p class="text-dark-500 text-xs">Total ARR</p></div>
        <div><p class="text-lg font-700 ${{churnColor}}">${{hasCh?d.churnCnt:'0'}}</p><p class="text-dark-500 text-xs">Churned Yesterday</p></div>
        <div><p class="text-lg font-700 ${{churnColor}}">${{((d.churnArr/(d.arr+d.churnArr))*100).toFixed(2)}}%</p><p class="text-dark-500 text-xs">Churn Rate</p></div>
      </div>
      ${{hasCh?`
      <div class="border-t border-dark-800 pt-3">
        <div class="churn-accordion" onclick="toggleChurn('${{accordionId}}',this)">
          <span class="chevron text-dark-400 text-xs mr-2">&#9654;</span>
          <span class="text-sm font-600 text-red-400">${{churnLabel}}</span>
        </div>
        <div class="churn-detail mt-3" id="${{accordionId}}">
          ${{churnRows}}
        </div>
      </div>
      `:`
      <div class="border-t border-dark-800 pt-3">
        <p class="text-emerald-400 text-sm font-500">&#10003; No churns yesterday</p>
      </div>
      `}}
    </div>`;
  }}).join('');
}}

function fmtChurnArr(v){{if(v>=1e6)return'$'+(v/1e6).toFixed(1)+'M';if(v>=1e3)return'$'+(v/1e3).toFixed(1)+'K';return'$'+v;}}

function renderOnboard(){{
  const el=document.getElementById('onboardList');
  if(!ONBOARD.length){{
    el.innerHTML='<div class="glass rounded-xl p-6 text-center"><p class="text-dark-400">No upcoming onboardings scheduled.</p></div>';
    return;
  }}
  const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function fmtD(s){{if(!s)return'<span class="text-dark-600">&mdash;</span>';const d=new Date(s+'T00:00:00');return months[d.getMonth()]+' '+d.getDate()+', '+d.getFullYear();}}
  function gapColor(g){{if(g===null)return'text-dark-500';if(g<=3)return'text-emerald-400';if(g<=7)return'text-amber-400';return'text-red-400';}}
  function untilBadge(u){{if(u===null)return'';if(u===0)return'<span class="ml-2 text-xs font-600 px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400">Today</span>';if(u===1)return'<span class="ml-2 text-xs font-600 px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">Tomorrow</span>';if(u<=7)return'<span class="ml-2 text-xs font-600 px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">'+u+' days</span>';return'<span class="ml-2 text-xs font-600 px-2 py-0.5 rounded bg-dark-700 text-dark-400">'+u+' days</span>';}}
  el.innerHTML=`
    <div class="glass rounded-xl overflow-hidden overflow-x-auto scrollbar-thin">
      <table class="w-full text-sm">
        <thead><tr class="border-b border-dark-800">
          <th class="px-3 py-3 text-left text-xs font-600 text-dark-400 uppercase tracking-wider">#</th>
          <th class="px-3 py-3 text-left text-xs font-600 text-dark-400 uppercase tracking-wider">Customer</th>
          <th class="px-3 py-3 text-left text-xs font-600 text-dark-400 uppercase tracking-wider">Pod</th>
          <th class="px-3 py-3 text-left text-xs font-600 text-dark-400 uppercase tracking-wider">Plan</th>
          <th class="px-3 py-3 text-left text-xs font-600 text-dark-400 uppercase tracking-wider">Sales Rep</th>
          <th class="px-3 py-3 text-right text-xs font-600 text-dark-400 uppercase tracking-wider">MRR</th>
          <th class="px-3 py-3 text-left text-xs font-600 text-dark-400 uppercase tracking-wider">First Payment</th>
          <th class="px-3 py-3 text-left text-xs font-600 text-dark-400 uppercase tracking-wider">Onboarding</th>
          <th class="px-3 py-3 text-right text-xs font-600 text-dark-400 uppercase tracking-wider cursor-help" title="Days between first Stripe payment and onboarding call. Lower is better — long waits increase early churn risk.">Wait Time</th>
          <th class="px-3 py-3 text-left text-xs font-600 text-dark-400 uppercase tracking-wider">Billing Period</th>
          <th class="px-3 py-3 text-left text-xs font-600 text-dark-400 uppercase tracking-wider">Renewal</th>
          <th class="px-3 py-3 text-left text-xs font-600 text-dark-400 uppercase tracking-wider">Links</th>
        </tr></thead>
        <tbody>
          ${{ONBOARD.map((q,i)=>`<tr class="border-b border-dark-800/50 hover:bg-dark-800/30 transition-colors">
            <td class="px-3 py-3 text-dark-500 text-xs">${{i+1}}</td>
            <td class="px-3 py-3 font-600 text-white">${{q.n}}</td>
            <td class="px-3 py-3 text-dark-400 text-xs">${{(POD_DISPLAY[q.pod]||q.pod)}}</td>
            <td class="px-3 py-3 text-dark-400 text-xs">${{q.pl||'&mdash;'}}</td>
            <td class="px-3 py-3 text-dark-400 text-xs">${{q.sr||'&mdash;'}}</td>
            <td class="px-3 py-3 text-right text-white font-600">${{q.mrr?'$'+q.mrr.toLocaleString():'&mdash;'}}</td>
            <td class="px-3 py-3 text-dark-400 text-xs">${{fmtD(q.sd)}}</td>
            <td class="px-3 py-3 text-white text-xs">${{fmtD(q.ob)}}${{untilBadge(q.until)}}</td>
            <td class="px-3 py-3 text-right"><span class="font-600 ${{gapColor(q.gap)}}">${{q.gap!==null?q.gap+' days':'&mdash;'}}</span></td>
            <td class="px-3 py-3 text-dark-400 text-xs">${{q.lp&&q.rd?fmtD(q.lp)+' &rarr; '+fmtD(q.rd):'&mdash;'}}</td>
            <td class="px-3 py-3 text-dark-400 text-xs">${{fmtD(q.rd)}}${{q.bc?' <span class="text-dark-600">('+q.bc+')</span>':''}}</td>
            <td class="px-3 py-3"><span class="inline-flex gap-2"><a href="https://app.attio.com/metric/workspaces/record/${{q.ri}}/overview" target="_blank" rel="noopener" class="text-purple-400/70 hover:text-purple-300 text-xs font-500 underline decoration-purple-400/30 hover:decoration-purple-300/60 transition-colors">Attio</a></span></td>
          </tr>`).join('')}}
        </tbody>
      </table>
    </div>
    <p class="text-dark-600 text-xs text-center mt-4">${{ONBOARD.length}} customer${{ONBOARD.length!==1?'s':''}} in onboarding queue</p>`;
}}

function toggleChurn(id,el){{
  el.classList.toggle('open');
  document.getElementById(id).classList.toggle('open');
}}

function fmt(v){{if(!v)return'<span class="text-dark-600">&mdash;</span>';if(v>=1e6)return'$'+(v/1e6).toFixed(1)+'M';if(v>=1e3)return'$'+(v/1e3).toFixed(0)+'K';return'$'+v;}}
function fmtSh(v){{if(!v)return'<span class="text-dark-600">&mdash;</span>';if(v>=1e6)return'<span class="text-emerald-400 font-600">$'+(v/1e6).toFixed(1)+'M</span>';if(v>=1e5)return'<span class="text-emerald-400">$'+(v/1e3).toFixed(0)+'K</span>';if(v>=1e3)return'$'+(v/1e3).toFixed(0)+'K';return'$'+v;}}
function stars(h){{if(h===null||h===undefined)return'<span class="text-dark-600 text-xs">Not rated</span>';const c={{1:'text-red-400',2:'text-orange-400',3:'text-amber-400',4:'text-emerald-400',5:'text-emerald-300'}};let s='';for(let i=1;i<=5;i++)s+=i<=h?'<span class="'+c[h]+'">\u2605</span>':'<span class="text-dark-700">\u2605</span>';return s;}}
function csBadge(cs){{if(cs===null||cs===undefined)return'<span class="text-dark-600">&mdash;</span>';if(cs===3)return'<span class="signal-tag bg-emerald-500/10 text-emerald-400">3</span>';if(cs===2)return'<span class="signal-tag bg-blue-500/10 text-blue-400">2</span>';return'<span class="signal-tag bg-dark-700 text-dark-300">1</span>';}}
function fmtDate(sd){{if(!sd)return'<span class="text-dark-600">&mdash;</span>';const d=new Date(sd+'T00:00:00');const m=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];return'<span class="text-dark-400 text-xs">'+m[d.getMonth()]+' \\''+String(d.getFullYear()).slice(2)+'</span>';}}
function retBadge(r){{const p=Math.round(r*100);let c='text-red-400 bg-red-500/10';if(p>=80)c='text-emerald-400 bg-emerald-500/10';else if(p>=60)c='text-amber-400 bg-amber-500/10';else if(p>=40)c='text-orange-400 bg-orange-500/10';return`<span class="signal-tag ${{c}}">${{p}}%</span>`;}}
function sigTags(sigs){{const cm={{'LTV UP':'bg-emerald-500/10 text-emerald-400','CHURN':'bg-red-500/10 text-red-400','IDLE':'bg-amber-500/10 text-amber-400','INT.ERR':'bg-orange-500/10 text-orange-400','UPSELL':'bg-cyan-500/10 text-cyan-400','REVSHARE':'bg-teal-500/10 text-teal-400','NEW':'bg-dark-700 text-dark-300'}};return sigs.map(s=>{{let c='bg-dark-700 text-dark-300';for(const[k,v]of Object.entries(cm))if(s.includes(k)){{c=v;break;}};if(s.includes('ROAS'))c=s.includes('\u2605')?'bg-emerald-500/10 text-emerald-400':s.includes('\u2713')?'bg-blue-500/10 text-blue-400':'bg-amber-500/10 text-amber-400';return`<span class="signal-tag ${{c}}">${{s}}</span>`;}}).join(' ');}}
function tierCls(t){{return{{1:'tier-1-row',2:'tier-2-row',3:'tier-3-row',4:'tier-4-row'}}[t]||'';}}
function podLabel(p){{return POD_DISPLAY[p]||p;}}
const POD_DISPLAY={{'Marcus+Martin':'Angus','Sebastian+Daniel':'Belgian Blue','Aimy+Espen':'Charolais','Nicklas+Hamsa':'Buffalo'}};
const POD_MEMBERS={{'Marcus+Martin':'Marcus & Martin','Sebastian+Daniel':'Sebastian & Daniel','Aimy+Espen':'Aimy & Espen','Nicklas+Hamsa':'Nicklas & Hamsa'}};
function podColor(p){{const m={{'Marcus+Martin':'blue','Sebastian+Daniel':'purple','Aimy+Espen':'pink','Nicklas+Hamsa':'teal'}};return m[p]||'blue';}}
function stripeLink(wsId){{if(!wsId)return'<span class="text-dark-700">&mdash;</span>';return`<a href="https://dashboard.stripe.com/subscriptions/${{wsId}}" target="_blank" rel="noopener" class="text-blue-400/70 hover:text-blue-300 text-xs font-500 underline decoration-blue-400/30 hover:decoration-blue-300/60 transition-colors">Stripe</a>`;}}
function attioLink(recId){{if(!recId)return'<span class="text-dark-700">&mdash;</span>';return`<a href="https://app.attio.com/metric/workspaces/record/${{recId}}/overview" target="_blank" rel="noopener" class="text-purple-400/70 hover:text-purple-300 text-xs font-500 underline decoration-purple-400/30 hover:decoration-purple-300/60 transition-colors">Attio</a>`;}}

function updateKPIs(){{
  const el=document.getElementById('kpiCards');
  let ws,arr,ltv,risk,rated,total;
  if(curPod==='all'){{ws=TOTAL.ws;arr=TOTAL.arr;ltv=TOTAL.ltv;risk=TOTAL.risk;rated=D.filter(w=>w.h!==null).length;total=TOTAL.ws;}}
  else{{const pm=PM[curPod];ws=pm.cnt;arr=pm.arr;ltv=pm.ltv;risk=pm.risk;rated=pm.rated;total=pm.cnt;}}
  el.innerHTML=`
    <div class="glass rounded-xl p-4 sm:p-5"><p class="text-dark-500 text-xs font-medium uppercase tracking-wider mb-1">Pod ARR</p><p class="text-2xl sm:text-3xl font-800 text-white">${{fmt(arr)}}</p><p class="text-dark-500 text-xs mt-1">${{ws}} active workspaces</p></div>
    <div class="glass rounded-xl p-4 sm:p-5"><p class="text-dark-500 text-xs font-medium uppercase tracking-wider mb-1">Est. 2-Year LTV</p><p class="text-2xl sm:text-3xl font-800 text-emerald-400">${{fmt(ltv)}}</p><p class="text-dark-500 text-xs mt-1">Based on current signals</p></div>
    <div class="glass rounded-xl p-4 sm:p-5"><p class="text-dark-500 text-xs font-medium uppercase tracking-wider mb-1">Health Rated</p><p class="text-2xl sm:text-3xl font-800 text-amber-400">${{rated}} <span class="text-lg text-dark-500">/ ${{total}}</span></p><p class="text-dark-500 text-xs mt-1">${{total-rated}} unrated (blind spot)</p></div>
    <div class="glass rounded-xl p-4 sm:p-5"><p class="text-dark-500 text-xs font-medium uppercase tracking-wider mb-1">At Risk (Health 1-3)</p><p class="text-2xl sm:text-3xl font-800 text-red-400">${{risk}}</p><p class="text-dark-500 text-xs mt-1">Documented retention plans</p></div>`;
}}

function updateCSMSplit(){{
  const el=document.getElementById('csmSplit');
  if(curPod==='all'){{el.innerHTML='';return;}}
  const pm=PM[curPod];
  el.innerHTML=pm.csms.map(c=>`
    <div class="glass rounded-xl p-4 sm:p-5">
      <div class="flex items-center gap-3 mb-3">
        <div class="w-8 h-8 rounded-full bg-${{c.cl}}-500/20 flex items-center justify-center text-${{c.cl}}-400 text-sm font-bold">${{c.n[0]}}</div>
        <div><p class="text-white font-600">${{c.n}} <span class="text-dark-400 font-400 text-sm">${{c.role}}</span></p></div>
      </div>
      <div class="grid grid-cols-3 gap-3 text-center">
        <div><p class="text-lg font-700 text-white">${{c.cnt}}</p><p class="text-dark-500 text-xs">Workspaces</p></div>
        <div><p class="text-lg font-700 text-white">${{fmt(c.arr)}}</p><p class="text-dark-500 text-xs">ARR</p></div>
        <div><p class="text-lg font-700 ${{c.unr>5?'text-amber-400':'text-emerald-400'}}">${{c.unr}} unrated</p><p class="text-dark-500 text-xs">Health gap</p></div>
      </div>
    </div>`).join('');
}}

function updateTierFilters(){{
  const el=document.getElementById('tierFilters');
  let filtered=D;
  if(curPod!=='all')filtered=D.filter(w=>w.p===curPod);
  const tiers={{1:0,2:0,3:0,4:0}};
  filtered.forEach(w=>tiers[w.t]++);
  const total=filtered.length;
  el.innerHTML=`
    <button onclick="filterTier('all')" class="filter-btn ${{curTier==='all'?'bg-dark-800 text-dark-200':'bg-dark-800/50 text-dark-400'}} px-3 py-1.5 rounded-lg text-xs font-600 hover:bg-dark-700 transition" data-tier="all">All (${{total}})</button>
    <button onclick="filterTier(1)" class="filter-btn ${{curTier===1?'bg-dark-800 text-dark-200':'bg-dark-800/50 text-dark-400'}} px-3 py-1.5 rounded-lg text-xs font-600 hover:bg-dark-700 transition" data-tier="1">T1 (${{tiers[1]}})</button>
    <button onclick="filterTier(2)" class="filter-btn ${{curTier===2?'bg-dark-800 text-dark-200':'bg-dark-800/50 text-dark-400'}} px-3 py-1.5 rounded-lg text-xs font-600 hover:bg-dark-700 transition" data-tier="2">T2 (${{tiers[2]}})</button>
    <button onclick="filterTier(3)" class="filter-btn ${{curTier===3?'bg-dark-800 text-dark-200':'bg-dark-800/50 text-dark-400'}} px-3 py-1.5 rounded-lg text-xs font-600 hover:bg-dark-700 transition" data-tier="3">T3 (${{tiers[3]}})</button>
    <button onclick="filterTier(4)" class="filter-btn ${{curTier===4?'bg-dark-800 text-dark-200':'bg-dark-800/50 text-dark-400'}} px-3 py-1.5 rounded-lg text-xs font-600 hover:bg-dark-700 transition" data-tier="4">T4 (${{tiers[4]}})</button>`;
}}

function updateCSMFilters(){{
  const el=document.getElementById('csmFilters');
  if(curPod==='all'){{el.innerHTML='';return;}}
  const pm=PM[curPod];
  let html=`<button onclick="filterCSM('all')" class="csm-btn ${{curCSM==='all'?'bg-dark-800 text-dark-200':'bg-dark-800/50 text-dark-400'}} px-3 py-1.5 rounded-lg text-xs font-600 hover:bg-dark-700 transition" data-csm="all">Both</button>`;
  pm.csms.forEach(c=>{{html+=`<button onclick="filterCSM('${{c.n}}')" class="csm-btn ${{curCSM===c.n?'bg-dark-800 text-dark-200':'bg-dark-800/50 text-dark-400'}} px-3 py-1.5 rounded-lg text-xs font-600 hover:bg-dark-700 transition" data-csm="${{c.n}}">${{c.n}}</button>`;}});
  el.innerHTML=html;
}}

// Sort state
let sortKey='pi',sortDir='desc';
// Column filters
let colFilters={{plan:new Set(),health:new Set(),pod:new Set(),csm:new Set(),sig:new Set(),cs:new Set()}};

function sortCol(th){{
  const key=th.dataset.sort;
  if(!key)return;
  if(sortKey===key){{sortDir=sortDir==='asc'?'desc':'asc';}}
  else{{sortKey=key;sortDir=(key==='n'||key==='sd'?'asc':'desc');}}
  document.querySelectorAll('#headerRow th.sortable').forEach(t=>{{t.classList.remove('asc','desc');}});
  th.classList.add(sortDir);
  th.querySelector('.sort-arrow').innerHTML=sortDir==='asc'?'&#9650;':'&#9660;';
  renderTable();
}}
// Attach sort handlers to sort-arrow spans only
document.querySelectorAll('#headerRow th[data-sortable] .sort-arrow').forEach(function(arrow){{
  arrow.style.cursor='pointer';
  arrow.addEventListener('click',function(e){{
    e.stopPropagation();
    sortCol(arrow.closest('th'));
  }});
}});

function getFilteredData(){{
  const search=document.getElementById('searchInput').value.toLowerCase();
  return D.filter(w=>{{
    if(curPod!=='all'&&w.p!==curPod)return false;
    if(curTier!=='all'&&w.t!==curTier)return false;
    if(curCSM!=='all'&&w.c!==curCSM)return false;
    if(search&&!w.n.toLowerCase().includes(search))return false;
    if(colFilters.plan.size&&!colFilters.plan.has(w.pl))return false;
    if(colFilters.health.size){{const hk=w.h===null?'Not rated':String(w.h);if(!colFilters.health.has(hk))return false;}}
    if(colFilters.pod.size&&!colFilters.pod.has(w.p))return false;
    if(colFilters.csm.size&&!colFilters.csm.has(w.c))return false;
    if(colFilters.sig.size&&!w.s.some(s=>colFilters.sig.has(s)))return false;
    if(colFilters.cs.size){{const ck=w.cs===null?'Not set':String(w.cs);if(!colFilters.cs.has(ck))return false;}}
    return true;
  }});
}}

function renderTable(){{
  let filtered=getFilteredData();
  filtered.sort((a,b)=>{{
    let va=a[sortKey],vb=b[sortKey];
    if(sortKey==='h'){{va=va===null?-1:va;vb=vb===null?-1:vb;}}
    if(sortKey==='cs'){{va=va===null?-1:va;vb=vb===null?-1:vb;}}
    if(sortKey==='sd'){{va=va||'';vb=vb||'';return sortDir==='asc'?va.localeCompare(vb):vb.localeCompare(va);}}
    if(sortKey==='n'){{va=(va||'').toLowerCase();vb=(vb||'').toLowerCase();return sortDir==='asc'?va.localeCompare(vb):vb.localeCompare(va);}}
    if(typeof va==='number'||typeof vb==='number'){{va=va||0;vb=vb||0;}}
    return sortDir==='asc'?(va-vb):(vb-va);
  }});
  const tbody=document.getElementById('tableBody');
  tbody.innerHTML=filtered.map((w,i)=>`
    <tr class="workspace-row border-b border-dark-800/50 ${{tierCls(w.t)}}">
      <td class="px-3 py-2.5 text-dark-500 text-xs font-500">${{i+1}}</td>
      <td class="px-3 py-2.5 text-xs"><div class="font-600 text-white overflow-hidden text-ellipsis whitespace-nowrap" title="${{w.n}}">${{w.n}}</div><div class="flex gap-2 mt-0.5">${{stripeLink(w.w)}} ${{attioLink(w.ri)}}</div></td>
      <td class="px-3 py-2.5 text-xs"><span class="text-dark-400">${{w.p.split('+')[0].slice(0,3)}}</span></td>
      <td class="px-3 py-2.5 text-xs"><span class="px-2 py-0.5 rounded bg-${{podColor(w.p)}}-500/10 text-${{podColor(w.p)}}-400">${{w.c}}</span></td>
      <td class="px-3 py-2.5 text-xs">${{fmtDate(w.sd)}}</td>
      <td class="px-3 py-2.5 text-xs text-dark-300">${{w.pl}}</td>
      <td class="px-3 py-2.5 text-center text-xs">${{stars(w.h)}}</td>
      <td class="px-3 py-2.5 text-center text-xs">${{csBadge(w.cs)}}</td>
      <td class="px-3 py-2.5 text-right text-sm font-500 text-white">${{fmt(w.a)}}</td>
      <td class="px-3 py-2.5 text-right text-sm font-500 text-white">${{fmt(w.l)}}</td>
      <td class="px-3 py-2.5 text-right text-sm">${{fmtSh(w.sh)}}</td>
      <td class="px-3 py-2.5 text-right text-xs ${{w.ar>=5?'text-emerald-400 font-600':w.ar>=2?'text-blue-400':w.ar>0?'text-dark-400':'text-dark-600'}}">${{w.ar?w.ar.toFixed(1)+'x':'&mdash;'}}</td>
      <td class="px-3 py-2.5 text-center">${{retBadge(w.ret)}}</td>
      <td class="px-3 py-2.5"><div class="flex gap-1 flex-wrap">${{sigTags(w.s)}}</div></td>
      <td class="px-3 py-2.5 text-xs text-dark-400 min-w-[200px]">${{w.act}}</td>
    </tr>`).join('');
}}

// Column filter dropdowns
function buildDropdowns(){{
  const plans=[...new Set(D.map(w=>w.pl))].sort();
  const healths=['5','4','3','2','1','Not rated'];
  const pods=[...new Set(D.map(w=>w.p))].sort();
  const csms=[...new Set(D.map(w=>w.c))].sort();
  const sigs=[...new Set(D.flatMap(w=>w.s))].sort();
  const css=['3','2','1','Not set'];
  fillDrop('dropPlan',plans,'plan');
  fillDrop('dropHealth',healths,'health');
  fillDrop('dropPod',pods,'pod');
  fillDrop('dropCSM',csms,'csm');
  fillDrop('dropSig',sigs,'sig');
  fillDrop('dropCS',css,'cs');
}}

function fillDrop(id,items,filterKey){{
  const el=document.getElementById(id);
  el.innerHTML='<label class="text-dark-500 font-600 text-xs px-3 py-1" style="cursor:pointer" onclick="clearColFilter(\\''+filterKey+'\\')">Clear all</label>'+
    items.map(v=>'<label><input type="checkbox" value="'+v+'" onchange="onColFilter(\\''+filterKey+'\\',this)"> '+v+'</label>').join('');
}}

function onColFilter(key,cb){{
  if(cb.checked)colFilters[key].add(cb.value);
  else colFilters[key].delete(cb.value);
  // Highlight filter button
  const dropId={{plan:'dropPlan',health:'dropHealth',pod:'dropPod',csm:'dropCSM',sig:'dropSig',cs:'dropCS'}}[key];
  const btn=document.getElementById(dropId).previousElementSibling;
  btn.classList.toggle('active',colFilters[key].size>0);
  renderTable();
}}

function clearColFilter(key){{
  colFilters[key].clear();
  const dropId={{plan:'dropPlan',health:'dropHealth',pod:'dropPod',csm:'dropCSM',sig:'dropSig',cs:'dropCS'}}[key];
  document.getElementById(dropId).querySelectorAll('input').forEach(cb=>cb.checked=false);
  const btn=document.getElementById(dropId).previousElementSibling;
  btn.classList.remove('active');
  renderTable();
}}

function toggleDrop(ev,id){{
  ev.stopPropagation();
  ev.preventDefault();
  const el=document.getElementById(id);
  // Close others
  document.querySelectorAll('.col-dropdown.show').forEach(d=>{{if(d.id!==id)d.classList.remove('show');}});
  el.classList.toggle('show');
}}

// Close dropdowns when clicking outside
document.addEventListener('click',()=>{{document.querySelectorAll('.col-dropdown.show').forEach(d=>d.classList.remove('show'));}});

function selectPod(p){{
  curPod=p;curTier='all';curCSM='all';
  // Reset column filters when switching pods
  Object.keys(colFilters).forEach(k=>colFilters[k].clear());
  document.querySelectorAll('.col-dropdown input').forEach(cb=>cb.checked=false);
  document.querySelectorAll('.col-filter-btn').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.pod-tab').forEach(b=>{{
    const active=b.dataset.pod===p;
    b.classList.toggle('active',active);
    b.classList.toggle('bg-dark-800/50',active);
    b.classList.toggle('text-dark-400',active);
    b.classList.toggle('bg-dark-800/30',!active);
    b.classList.toggle('text-dark-500',!active);
  }});
  updateKPIs();updateCSMSplit();updateTierFilters();updateCSMFilters();renderTable();
}}

function filterTier(t){{curTier=t;updateTierFilters();renderTable();}}
function filterCSM(c){{curCSM=c;updateCSMFilters();renderTable();}}
function applyFilters(){{renderTable();}}

// Init
buildDropdowns();
if(!document.getElementById('dashboard').classList.contains('locked')){{selectPod('all');renderDailyCards();}}

// Scroll hint — hide once user scrolls right
const scrollEl=document.getElementById('tableScroll');
const hintEl=document.getElementById('scrollHint');
if(scrollEl&&hintEl){{scrollEl.addEventListener('scroll',function(){{if(scrollEl.scrollLeft>20)hintEl.style.opacity='0';else hintEl.style.opacity='1';}});hintEl.style.transition='opacity 0.3s';}}

// Column resize — must be called after table is visible (after unlock)
let resizeInited=false;
let colWidths=[];
function lockTableLayout(){{
  const table=document.getElementById('mainTable');
  if(!table||table.dataset.locked)return;
  const ths=table.querySelectorAll('thead th');
  colWidths=[];
  ths.forEach(function(th){{colWidths.push(th.offsetWidth);}});
  table.style.tableLayout='fixed';
  table.style.width=colWidths.reduce((a,b)=>a+b,0)+'px';
  ths.forEach(function(th,i){{th.style.width=colWidths[i]+'px';}});
  table.dataset.locked='1';
}}
function initColResize(){{
  if(resizeInited)return;
  const table=document.getElementById('mainTable');
  if(!table)return;
  const ths=table.querySelectorAll('thead th');
  requestAnimationFrame(function(){{
    ths.forEach(function(th,i){{
      if(i===ths.length-1)return;
      const handle=document.createElement('div');
      handle.className='col-resize';
      th.appendChild(handle);
      handle.addEventListener('mousedown',function(e){{
        e.preventDefault();
        e.stopPropagation();
        lockTableLayout();
        const startX=e.pageX;
        const startW=th.offsetWidth;
        const tableStartW=table.offsetWidth;
        handle.classList.add('active');
        document.body.style.cursor='col-resize';
        document.body.style.userSelect='none';
        function onMove(e2){{
          const nw=Math.max(30,startW+(e2.pageX-startX));
          th.style.width=nw+'px';
          table.style.width=(tableStartW-startW+nw)+'px';
        }}
        function onUp(){{
          handle.classList.remove('active');
          document.body.style.cursor='';
          document.body.style.userSelect='';
          document.removeEventListener('mousemove',onMove);
          document.removeEventListener('mouseup',onUp);
        }}
        document.addEventListener('mousemove',onMove);
        document.addEventListener('mouseup',onUp);
      }});
    }});
    resizeInited=true;
  }});
}}

// Password auth
const PW_HASH='{PW_HASH}';
async function sha256(msg){{const buf=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(msg));return[...new Uint8Array(buf)].map(b=>b.toString(16).padStart(2,'0')).join('');}}
async function checkPw(){{
  const pw=document.getElementById('pwInput').value;
  const h=await sha256(pw);
  if(h===PW_HASH){{
    sessionStorage.setItem('csm_auth','1');
    unlock();
  }}else{{
    document.getElementById('pwError').classList.remove('hidden');
    document.getElementById('pwInput').value='';
    document.getElementById('pwInput').focus();
  }}
  return false;
}}
function unlock(){{
  document.getElementById('authGate').classList.add('hidden');
  document.getElementById('dashboard').classList.remove('locked');
  renderDailyCards();
  selectPod('all');
  initColResize();
}}
if(sessionStorage.getItem('csm_auth')==='1')unlock();
</script>
</body>
</html>'''

    return html


# ─── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("CSM Pod Dashboard Builder")
    print("=" * 60)

    # 1. Load and parse
    print("\n[1/4] Loading and parsing data files...")
    workspaces = load_and_parse()
    print(f"  Loaded {len(workspaces)} unique workspaces")

    # 2. Compute LTV
    print("\n[2/4] Computing LTV model...")
    workspaces = build_workspace_data(workspaces)

    # Summary stats
    total_arr = sum(w["arr"] for w in workspaces)
    total_ltv = sum(w["ltv"] for w in workspaces)
    rated = sum(1 for w in workspaces if w["health"] is not None)
    unrated = sum(1 for w in workspaces if w["health"] is None)
    t1 = sum(1 for w in workspaces if w["tier"] == 1)
    t2 = sum(1 for w in workspaces if w["tier"] == 2)
    t3 = sum(1 for w in workspaces if w["tier"] == 3)
    t4 = sum(1 for w in workspaces if w["tier"] == 4)
    with_cs = sum(1 for w in workspaces if w["est_ltv"] is not None)
    with_sd = sum(1 for w in workspaces if w["start_date"] is not None)

    print(f"  Total workspaces: {len(workspaces)}")
    print(f"  Total ARR: ${total_arr:,.0f}")
    print(f"  Total 2yr LTV: ${total_ltv:,.0f}")
    print(f"  Health rated: {rated} / {len(workspaces)} ({unrated} unrated)")
    print(f"  With Customer Score: {with_cs} / {len(workspaces)}")
    print(f"  With Start Date: {with_sd} / {len(workspaces)}")
    print(f"  Tiers: T1={t1}, T2={t2}, T3={t3}, T4={t4}")

    # Pod breakdown
    pods = {}
    for w in workspaces:
        pod = w["pod"]
        if pod not in pods:
            pods[pod] = []
        pods[pod].append(w)

    print("\n  Pod breakdown:")
    for pod_name in ["Marcus+Martin", "Sebastian+Daniel", "Aimy+Espen", "Nicklas+Hamsa"]:
        if pod_name in pods:
            pw = pods[pod_name]
            print(f"    {pod_name}: {len(pw)} workspaces, ARR=${sum(w['arr'] for w in pw):,.0f}, LTV=${sum(w['ltv'] for w in pw):,.0f}")

    # Top 5
    print("\n  Top 5 by priority:")
    for w in workspaces[:5]:
        print(f"    {w['name']}: priority=${w['priority']:,.0f}, LTV=${w['ltv']:,.0f}, tier={w['tier']}")

    # 3. Generate HTML
    print("\n[3/4] Generating HTML dashboard...")
    js_data = generate_js_data(workspaces)
    pm_js, total_js, stats = compute_pod_meta(workspaces)
    daily_js = compute_daily_churn(workspaces)
    onboard_js = compute_onboarding_queue(workspaces)
    html = generate_html(js_data, pm_js, total_js, daily_js, onboard_js, stats)

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Written: {OUTPUT_PATH}")
    print(f"  Size: {len(html):,} bytes")

    # 4. Copy to docs
    print("\n[4/4] Copying to docs/...")
    os.makedirs(os.path.dirname(DOCS_PATH), exist_ok=True)
    shutil.copy2(OUTPUT_PATH, DOCS_PATH)
    print(f"  Copied: {DOCS_PATH}")

    print("\n" + "=" * 60)
    print("Done! Dashboard generated successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
