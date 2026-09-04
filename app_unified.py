import os
import base64
import csv
from datetime import datetime
from io import BytesIO
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from scipy.optimize import curve_fit
from flask import Flask, render_template_string, request, jsonify, send_file, session, redirect, url_for, flash
from flaskwebgui import FlaskUI
from flask_cors import CORS

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable, Image as RLImage, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

# --- HTML TEMPLATES ---

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - SANO AI-Precision Oncology Platform</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light d-flex align-items-center justify-content-center" style="height: 100vh;">
    <div class="card shadow-sm p-4" style="width: 350px;">
        <div class="text-center mb-4">
            <h5 class="fw-bold text-primary">SANO AI Platform</h5>
            <p class="text-muted small">Authorized Access Only</p>
        </div>
        
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div class="alert alert-danger py-2 px-3 small">{{ messages[0] }}</div>
          {% endif %}
        {% endwith %}

        <form method="POST" action="/login">
            <div class="mb-3">
                <label class="form-label fw-bold small">Username</label>
                <input type="text" name="username" class="form-control" required>
            </div>
            <div class="mb-4">
                <label class="form-label fw-bold small">Password</label>
                <input type="password" name="password" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-primary w-100 fw-bold">Login to System</button>
        </form>
    </div>
</body>
</html>
"""

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SANO AI-Precision Oncology Platform</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #F1F5F9; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
        .header-bg { background-color: #0B2545; color: white; }
        .section-title { background-color: #E2E8F0; padding: 8px 12px; font-weight: bold; border-radius: 4px; margin-top: 20px; }
        .matrix-input { font-size: 0.85rem; padding: 4px; border: 1px solid #ced4da; border-radius: 4px; width: 100%; text-align: center; }
        .preview-box img { height: 100px; border-radius: 4px; margin-right: 10px; border: 1px solid #CBD5E1; }
        .result-img-container { text-align: center; background: white; padding: 15px; border-radius: 8px; border: 1px solid #CBD5E1; }
        #drug_matrix th, #drug_matrix td { padding: 4px 6px; }
        .logo-img { height: 40px; }
    </style>
</head>
<body>

<div class="container-fluid header-bg py-3 px-4 d-flex justify-content-between align-items-center">
    <div class="d-flex align-items-center">
        <img src="BioArchitec logo_latest.png" class="logo-img me-3" alt="Logo" onerror="this.style.display='none'">
        <h4 class="mb-0" id="ui_title">SANO AI-Precision Oncology Platform</h4>
    </div>
    <div>
        <button class="btn btn-outline-light btn-sm me-2" onclick="toggleLang()" id="lang_toggle">Switch to 中文</button>
        <a href="/logout" class="btn btn-outline-danger btn-sm">Logout</a>
    </div>
</div>

<div class="container bg-white shadow-sm my-4 p-4 rounded">
    <div class="row mb-3">
        <div class="col-md-4">
            <label class="form-label fw-bold" id="cancer_type_lbl">Select Cancer Type:</label>
            <select class="form-select" id="cancer_combo" onchange="handleCancerTypeChange()">
                <option value="c_crc">Colorectal Cancer (mCRC)</option>
                <option value="c_sclc">Non-Small Cell Lung Cancer (NSCLC)</option>
                <option value="c_hcc">Liver Cancer (HCC)</option>
            </select>
        </div>
    </div>

    <div class="section-title" id="sec_sum">Clinical Executive Summary</div>
    <textarea class="form-control mt-2 bg-light text-primary fw-bold" id="p_summary" rows="5" readonly></textarea>

    <div class="section-title" id="sec1">1. Patient & Clinical Information</div>
    <div class="row g-3 mt-1">
        <div class="col-md-3"><label class="fw-bold" id="lbl_id">Patient ID:</label><input type="text" class="form-control form-control-sm" id="p_id" value="Z2400023"></div>
        <div class="col-md-3"><label class="fw-bold" id="lbl_gender">Gender / Age:</label><input type="text" class="form-control form-control-sm" id="p_gender" value="Female / 52"></div>
        <div class="col-md-3"><label class="fw-bold" id="lbl_diag">Diagnosis:</label><input type="text" class="form-control form-control-sm" id="p_diag" value=""></div>
        <div class="col-md-3"><label class="fw-bold" id="lbl_stage">TNM Stage:</label><input type="text" class="form-control form-control-sm" id="p_stage" value="IV"></div>
        
        <div class="col-md-3"><label class="fw-bold" id="lbl_sub_unit">Submission Unit:</label><input type="text" class="form-control form-control-sm" id="p_sub_unit"></div>
        <div class="col-md-3"><label class="fw-bold" id="lbl_test_unit">Testing Unit:</label><input type="text" class="form-control form-control-sm" id="p_test_unit"></div>
        
        <div class="col-md-4">
            <label class="fw-bold" id="lbl_samp_sit">Sample Situation:</label>
            <div class="input-group input-group-sm">
                <input type="number" class="form-control text-center" id="p_dim_l" placeholder="L">
                <span class="input-group-text">mm*</span>
                <input type="number" class="form-control text-center" id="p_dim_w" placeholder="W">
                <span class="input-group-text">mm*</span>
                <input type="number" class="form-control text-center" id="p_dim_h" placeholder="H">
                <span class="input-group-text">mm; </span>
                <input type="number" class="form-control text-center" id="p_weight" placeholder="Wgt">
                <span class="input-group-text">mg</span>
            </div>
        </div>
        
        <div class="col-md-2">
            <label class="fw-bold" id="lbl_sample">Sample Type:</label>
            <select class="form-select form-select-sm" id="p_sample">
                <option value="Surgical Resection" id="opt_surg">Surgical Resection</option>
                <option value="Biopsy" id="opt_biop">Biopsy</option>
            </select>
        </div>
        
        <div class="col-md-6"><label class="fw-bold" id="lbl_prior">Prior Therapy:</label><input type="text" class="form-control form-control-sm" id="p_prior" value="None"></div>
        <div class="col-md-6"><label class="fw-bold" id="lbl_date">Report Date:</label><input type="text" class="form-control form-control-sm" id="p_date"></div>
        
        <div class="col-md-12 mt-3">
            <label class="fw-bold" id="lbl_surg_photo">Upload Surgical Sample Photo:</label>
            <input type="file" class="form-control form-control-sm" id="surg_image" accept="image/*" onchange="previewSurgImage()">
            <div id="surg-preview" class="preview-box mt-2 d-flex"></div>
        </div>
    </div>

    <div class="section-title" id="sec2">2. Biomarker Profile (NGS Panel)</div>
    <div class="row g-3 mt-1" id="biomarker_container">
        <!-- Injected via JS -->
    </div>

    <div class="section-title" id="sec3">3. PDO Modeling Information</div>
    <div class="row g-3 mt-1">
        <div class="col-md-4"><label class="fw-bold" id="lbl_seed">Seeding Date:</label><input type="text" class="form-control form-control-sm" id="p_seed"></div>
        <div class="col-md-4"><label class="fw-bold" id="lbl_cell">Cell Volume:</label><input type="text" class="form-control form-control-sm" id="p_cell"></div>
        <div class="col-md-4"><label class="fw-bold" id="lbl_medium">Culture Medium:</label><input type="text" class="form-control form-control-sm" id="p_medium"></div>
        <div class="col-md-12">
            <label class="fw-bold" id="lbl_photo">Upload Microscopic Photos (Optional, Max 3):</label>
            <input type="file" class="form-control form-control-sm" id="pdo_images" accept="image/*" multiple onchange="previewPDOImages()">
            <div id="pdo-preview" class="preview-box mt-2 d-flex"></div>
        </div>
    </div>

    <div class="section-title" id="sec4">4. Drug Sensitivity Matrix & Prioritization</div>
    <div class="table-responsive mt-3">
        <table class="table table-bordered table-sm align-middle mb-2" id="drug_matrix">
            <thead class="table-light text-center" style="font-size:0.85rem;">
                <tr>
                    <th class="border-bottom-0"></th>
                    <th colspan="7" id="th_conc">Concentration</th>
                </tr>
                <tr>
                    <th style="width: 16%" class="border-top-0"></th>
                    <th style="width: 12%">Log10-7</th><th style="width: 12%">Log10-6</th><th style="width: 12%">Log10-5</th>
                    <th style="width: 12%">Log10-4</th><th style="width: 12%">Log10-3</th><th style="width: 12%">Log10-2</th><th style="width: 12%">Log10-1</th>
                </tr>
            </thead>
            <tbody id="drug_tbody">
                <!-- Injected via JS -->
            </tbody>
        </table>
    </div>
    
    <button class="btn btn-success btn-sm mb-3" id="btn_curve" onclick="generateCurve()">📊 Generate Drug Response Curve</button>
    
    <div id="curve_results" style="display:none;" class="mb-4">
        <div class="result-img-container shadow-sm">
            <img id="plot_img" src="" class="img-fluid" style="max-height: 400px;">
        </div>
    </div>

    <div class="section-title" id="sec6">Signatories</div>
    <div class="row g-3 mt-1 mb-5">
        <div class="col-md-6"><label class="fw-bold" id="lbl_tech">Testing Laboratory Technician:</label><input type="text" class="form-control form-control-sm" id="p_tech"></div>
        <div class="col-md-6"><label class="fw-bold" id="lbl_exam">Reviewing Clinical Examiner:</label><input type="text" class="form-control form-control-sm" id="p_exam"></div>
    </div>
</div>

<div class="container-fluid bg-light py-3 border-top d-flex justify-content-end position-fixed bottom-0 w-100">
    <button class="btn btn-primary" id="btn_export" onclick="requestExport()">Export Scientific Report (PDF)</button>
</div>

<div class="modal fade" id="authModal" tabindex="-1">
  <div class="modal-dialog modal-sm modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h6 class="modal-title fw-bold" id="modal_title">Authorisation Required</h6>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <label id="modal_lbl">Enter PDF Export Password:</label>
        <input type="password" id="export_pwd" class="form-control mt-2">
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-primary btn-sm w-100" id="modal_btn" onclick="verifyAndExport()">Confirm & Export</button>
      </div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    let currentLang = 'en';
    let base64Surg = [];
    let base64PDO = [];
    let generatedPlotB64 = "";
    let generatedResults = [];

    const DRUGS = {
        c_crc: { en: ["FOLFOX", "FOLFIRI", "Regorafenib", "Fruquintinib", "Oxaliplatin"], zh: ["FOLFOX", "FOLFIRI", "瑞戈非尼", "呋喹替尼", "奥沙利铂"] },
        c_sclc: { en: ["EP Regimen", "Irinotecan", "Topotecan", "Lurbinectedin", "Paclitaxel"], zh: ["EP 方案", "伊立替康", "拓扑替康", "芦比替定", "紫杉醇"] },
        c_hcc: { en: ["Atezolizumab+Bev", "Sorafenib", "Lenvatinib", "Regorafenib", "Cabozantinib"], zh: ["T+A 方案", "索拉非尼", "仑伐替尼", "瑞戈非尼", "卡博替尼"] }
    };

    const BIOMARKERS = {
        c_crc: { en: ["KRAS", "NRAS", "BRAF", "PIK3CA", "TP53", "APC", "SMAD4", "FBXW7", "CTNNB1", "ERBB2"], zh: ["KRAS", "NRAS", "BRAF", "PIK3CA", "TP53", "APC", "SMAD4", "FBXW7", "CTNNB1", "ERBB2"] },
        c_sclc: { en: ["EGRF", "ALK", "ROS1", "KRAS", "BRAF", "MET", "HER2", "RET", "NTRK1", "PIK3CA"], zh: ["EGRF", "ALK", "ROS1", "KRAS", "BRAF", "MET", "HER2", "RET", "NTRK1", "PIK3CA"] },
        c_hcc: { en: ["TP53", "CTNNB1", "TERT", "AXIN1", "ARID1A", "NFE2L2", "KEAP1", "TP73", "MET", "PTEN"], zh: ["TP53", "CTNNB1", "TERT", "AXIN1", "ARID1A", "NFE2L2", "KEAP1", "TP73", "MET", "PTEN"] }
    };

    const TEXT = {
        en: {
            ui_title: "SANO AI-Precision Oncology Platform", lang_toggle: "Switch to 中文", cancer_type_lbl: "Select Cancer Type:",
            sec_sum: "Clinical Executive Summary", sec1: "1. Patient & Clinical Information",
            lbl_id: "Patient ID:", lbl_gender: "Gender / Age:", lbl_diag: "Diagnosis:", lbl_stage: "TNM Stage:",
            lbl_sub_unit: "Submission Unit:", lbl_test_unit: "Testing Unit:", lbl_samp_sit: "Sample Situation:",
            lbl_sample: "Sample Type:", opt_surg: "Surgical Resection", opt_biop: "Biopsy", 
            lbl_prior: "Prior Therapy:", lbl_date: "Report Date:",
            lbl_surg_photo: "Upload Surgical Sample Photo:", sec2: "2. Biomarker Profile (NGS Panel)",
            sec3: "3. PDO Modeling Information", lbl_seed: "Seeding Date:", lbl_cell: "Cell Volume:", lbl_medium: "Culture Medium:", lbl_photo: "Upload Microscopic Photos:",
            sec4: "4. Drug Sensitivity Matrix & Prioritization", th_conc: "Concentration", btn_curve: "📊 Generate Drug Response Curve",
            sec6: "Signatories", lbl_tech: "Testing Laboratory Technician:", lbl_exam: "Reviewing Clinical Examiner:",
            btn_export: "Export Scientific Report (PDF)", modal_title: "Authorisation Required", modal_lbl: "Enter PDF Export Password:", modal_btn: "Confirm & Export",
            c_crc: "Colorectal Cancer (mCRC)", c_sclc: "Non-Small Cell Lung Cancer (NSCLC)", c_hcc: "Liver Cancer (HCC)",
            summary_default: "Summary will be created after drug response curves generation."
        },
        zh: {
            ui_title: "圣诺AI 肿瘤精准医疗平台", lang_toggle: "Switch to English", cancer_type_lbl: "选择癌症类型:",
            sec_sum: "临床解读总结", sec1: "1. 患者与临床信息",
            lbl_id: "病历号:", lbl_gender: "性别/年龄:", lbl_diag: "临床诊断:", lbl_stage: "TNM 分期:",
            lbl_sub_unit: "送检单位:", lbl_test_unit: "检测单位:", lbl_samp_sit: "样本状态:",
            lbl_sample: "样本类型:", opt_surg: "手术切除", opt_biop: "活检", 
            lbl_prior: "既往治疗:", lbl_date: "报告日期:",
            lbl_surg_photo: "上传手术样本照片:", sec2: "2. 生物标志物状态 (NGS Panel)",
            sec3: "3. 类器官(PDO)建模信息", lbl_seed: "接种日期:", lbl_cell: "接种细胞量:", lbl_medium: "培养基:", lbl_photo: "上传显微镜照片:",
            sec4: "4. 药物敏感性矩阵与优先级评估", th_conc: "浓度 (Concentration)", btn_curve: "📊 生成药物响应曲线",
            sec6: "报告签署人", lbl_tech: "测试实验室技术员:", lbl_exam: "临床审核员:",
            btn_export: "导出科学报告 (PDF)", modal_title: "需要授权", modal_lbl: "输入PDF导出密码:", modal_btn: "确认并导出",
            c_crc: "结直肠癌 (mCRC)", c_sclc: "非小细胞肺癌 (NSCLC)", c_hcc: "肝癌 (HCC)",
            summary_default: "生成药物响应曲线后将自动生成解读总结。"
        }
    };

    function setDateDefault() {
        const d = new Date();
        document.getElementById('p_date').value = ("0" + d.getDate()).slice(-2) + "/" + ("0" + (d.getMonth() + 1)).slice(-2) + "/" + d.getFullYear();
    }

    function toggleLang() {
        currentLang = currentLang === 'en' ? 'zh' : 'en';
        const t = TEXT[currentLang];
        
        ['ui_title', 'lang_toggle', 'cancer_type_lbl', 'sec_sum', 'sec1', 'lbl_id', 'lbl_gender', 'lbl_diag', 'lbl_stage', 
         'lbl_sub_unit', 'lbl_test_unit', 'lbl_samp_sit', 'lbl_sample', 'opt_surg', 'opt_biop', 'lbl_prior', 'lbl_date', 'lbl_surg_photo', 
         'sec2', 'sec3', 'lbl_seed', 'lbl_cell', 'lbl_medium', 'lbl_photo', 'sec4', 'th_conc', 'btn_curve', 
         'sec6', 'lbl_tech', 'lbl_exam', 'btn_export', 'modal_title', 'modal_lbl', 'modal_btn'].forEach(id => {
            document.getElementById(id).innerText = t[id];
        });

        const combo = document.getElementById('cancer_combo');
        combo.options[0].text = t.c_crc; combo.options[1].text = t.c_sclc; combo.options[2].text = t.c_hcc;
        
        handleCancerTypeChange();
        
        if (!generatedResults.length) {
            document.getElementById('p_summary').value = t.summary_default;
        } else {
            buildAutoSummary();
        }
    }

    function handleCancerTypeChange() {
        loadBiomarkers();
        loadDrugDefaults();
    }

    function loadBiomarkers() {
        const type = document.getElementById('cancer_combo').value;
        const b_list = BIOMARKERS[type][currentLang];
        const container = document.getElementById('biomarker_container');
        container.innerHTML = '';
        
        b_list.forEach((bm) => {
            const opt1 = currentLang === 'en' ? "Wild-type" : "野生型";
            const opt2 = currentLang === 'en' ? "Mutated" : "突变型";
            container.innerHTML += `
                <div class="col-md-3">
                    <label class="fw-bold b_name">${bm}:</label>
                    <select class="form-select form-select-sm b_val" onchange="buildAutoSummary()">
                        <option value="N/A">N/A</option><option value="${opt1}">${opt1}</option><option value="${opt2}">${opt2}</option>
                    </select>
                </div>
            `;
        });
    }

    function getRealisticCurve() {
        let r = [];
        r.push((98 + Math.random()*4).toFixed(1));
        r.push((90 + Math.random()*8).toFixed(1));
        r.push((70 + Math.random()*20).toFixed(1));
        r.push((40 + Math.random()*20).toFixed(1));
        r.push((15 + Math.random()*15).toFixed(1));
        r.push((5 + Math.random()*8).toFixed(1));
        r.push((1 + Math.random()*4).toFixed(1));
        return r;
    }

    function loadDrugDefaults() {
        const type = document.getElementById('cancer_combo').value;
        const panel = DRUGS[type][currentLang];
        const tbody = document.getElementById('drug_tbody');
        tbody.innerHTML = '';
        
        panel.forEach((drug, idx) => {
            let r1 = getRealisticCurve(), r2 = getRealisticCurve(), r3 = getRealisticCurve();
            tbody.innerHTML += `
                <tr>
                    <td rowspan="3" class="fw-bold text-center bg-light align-middle">${drug}</td>
                    ${r1.map(v => `<td><input type="number" class="matrix-input d_r1_${idx}" value="${v}"></td>`).join('')}
                </tr>
                <tr>${r2.map(v => `<td><input type="number" class="matrix-input d_r2_${idx}" value="${v}"></td>`).join('')}</tr>
                <tr>${r3.map(v => `<td><input type="number" class="matrix-input d_r3_${idx}" value="${v}"></td>`).join('')}</tr>
            `;
        });
    }

    function parseImage(files, arr, previewDiv, limit) {
        document.getElementById(previewDiv).innerHTML = '';
        arr.length = 0;
        for (let i = 0; i < Math.min(files.length, limit); i++) {
            const reader = new FileReader();
            const fName = files[i].name;
            reader.onload = e => {
                const img = document.createElement('img');
                img.src = e.target.result; 
                document.getElementById(previewDiv).appendChild(img);
                arr.push({ b64: e.target.result, name: fName });
            }
            reader.readAsDataURL(files[i]);
        }
    }

    function previewSurgImage() { parseImage(document.getElementById('surg_image').files, base64Surg, 'surg-preview', 1); }
    function previewPDOImages() { parseImage(document.getElementById('pdo_images').files, base64PDO, 'pdo-preview', 3); }

    function buildAutoSummary() {
        if (!generatedResults.length) return;
        const topDrug = generatedResults[0].name;
        const dL = document.getElementById('p_dim_l').value || "_";
        const dW = document.getElementById('p_dim_w').value || "_";
        const dH = document.getElementById('p_dim_h').value || "_";
        const wgt = document.getElementById('p_weight').value || "_";
        
        let selectedBioEN = [];
        let selectedBioZH = [];
        const b_names = document.querySelectorAll('.b_name');
        const b_vals = document.querySelectorAll('.b_val');
        
        for (let i = 0; i < b_names.length; i++) {
            if (b_vals[i].value !== "N/A") {
                const b_title = b_names[i].innerText.replace(':', '');
                selectedBioEN.push(`${b_title} (${b_vals[i].value})`);
                const zhVal = b_vals[i].value.includes("Wild-type") || b_vals[i].value.includes("野生型") ? "野生型" : "突变型";
                selectedBioZH.push(`${b_title} (${zhVal})`);
            }
        }
        
        const bioStrEN = selectedBioEN.length > 0 ? selectedBioEN.join(', ') : "None detected";
        const bioStrZH = selectedBioZH.length > 0 ? selectedBioZH.join('，') : "未检测到";
        
        const sumEN = `Diagnostic Insight: Patient ${document.getElementById('p_id').value} presented with ${document.getElementById('p_diag').value} (Stage: ${document.getElementById('p_stage').value}).\nSample Context: ${document.getElementById('p_sample').options[document.getElementById('p_sample').selectedIndex].text} received (${dL}mm*${dW}mm*${dH}mm, ${wgt}mg).\nBiomarker Profile: ${bioStrEN}.\nPharmacological Recommendation: According to in vitro sensitivity profiling, ${topDrug} represents the most optimal regimen, demonstrating robust cellular inhibition aligning with established treatment protocols.`;
        
        const sumZH = `诊断结论：患者 ${document.getElementById('p_id').value} 被诊断为 ${document.getElementById('p_diag').value}（分期：${document.getElementById('p_stage').value}）。\n样本背景：接收的 ${document.getElementById('p_sample').options[document.getElementById('p_sample').selectedIndex].text}（${dL}mm*${dW}mm*${dH}mm, ${wgt}mg）。\n生物标志物谱：${bioStrZH}。\n药理学建议：根据体外敏感性分析，${topDrug} 是最理想的方案，表现出强大的细胞抑制能力，符合既定治疗方案。`;
        
        document.getElementById('p_summary').value = currentLang === 'en' ? sumEN : sumZH;
    }

    async function generateCurve() {
        const type = document.getElementById('cancer_combo').value;
        const panel = DRUGS[type][currentLang];
        let drugsData = [];
        
        panel.forEach((drug, idx) => {
            const r1 = Array.from(document.querySelectorAll(`.d_r1_${idx}`)).map(i => i.value).join(',');
            const r2 = Array.from(document.querySelectorAll(`.d_r2_${idx}`)).map(i => i.value).join(',');
            const r3 = Array.from(document.querySelectorAll(`.d_r3_${idx}`)).map(i => i.value).join(',');
            drugsData.push({ name: drug, concs: "-7, -6, -5, -4, -3, -2, -1", rep1: r1, rep2: r2, rep3: r3 });
        });

        try {
            const response = await fetch('/api/plot', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({drugs: drugsData, lang: currentLang})
            });
            const data = await response.json();
            document.getElementById('plot_img').src = "data:image/png;base64," + data.plot;
            document.getElementById('curve_results').style.display = 'block';
            generatedPlotB64 = data.plot; generatedResults = data.results;
            
            buildAutoSummary();
        } catch (err) {
            alert("Error generating plot. Ensure Flask server is running.");
        }
    }

    function requestExport() { new bootstrap.Modal(document.getElementById('authModal')).show(); }

    async function verifyAndExport() {
        if (document.getElementById('export_pwd').value !== "BAPDO2026") {
            alert("Incorrect password! Authorization failed."); return;
        }

        let extractedBio = [];
        const b_names = document.querySelectorAll('.b_name');
        const b_vals = document.querySelectorAll('.b_val');
        for (let i = 0; i < b_names.length; i++) {
            extractedBio.push({ name: b_names[i].innerText.replace(':', ''), val: b_vals[i].value });
        }
        
        const dateRaw = document.getElementById('p_date').value.trim();
        const dateFormatted = dateRaw.replace(/\//g, '');
        const patId = document.getElementById('p_id').value.trim();
        const dl_name = currentLang === 'zh' ? 
            `柏奧雅德个性化类器官药敏科学报告_${patId}_${dateFormatted}.pdf` : 
            `BioArchitec PDO-DST Sci Report_${patId}_${dateFormatted}.pdf`;

        const payload = {
            lang: currentLang, dl_name: dl_name, patient_id: patId, gender_age: document.getElementById('p_gender').value,
            diagnosis: document.getElementById('p_diag').value, stage: document.getElementById('p_stage').value,
            sub_unit: document.getElementById('p_sub_unit').value, test_unit: document.getElementById('p_test_unit').value,
            samp_sit: `${document.getElementById('p_dim_l').value}mm*${document.getElementById('p_dim_w').value}mm*${document.getElementById('p_dim_h').value}mm; ${document.getElementById('p_weight').value}mg`,
            sample_type: document.getElementById('p_sample').options[document.getElementById('p_sample').selectedIndex].text,
            prior_therapy: document.getElementById('p_prior').value, report_date: dateRaw,
            biomarkers: extractedBio, seed_date: document.getElementById('p_seed').value,
            cell_count: document.getElementById('p_cell').value, medium: document.getElementById('p_medium').value,
            summary_text: document.getElementById('p_summary').value, tech_name: document.getElementById('p_tech').value,
            exam_name: document.getElementById('p_exam').value, surg_image: base64Surg, pdo_images: base64PDO,
            plot_b64: generatedPlotB64, results: generatedResults
        };

        try {
            const response = await fetch('/api/export', {
                method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a'); a.href = url;
                a.download = dl_name;
                document.body.appendChild(a); a.click(); a.remove();
                bootstrap.Modal.getInstance(document.getElementById('authModal')).hide();
            } else {
                alert("Server error occurred during export.");
            }
        } catch (err) {
            alert("Network error. Ensure Flask server is running.");
        }
    }

    window.onload = () => { 
        setDateDefault(); 
        document.getElementById('p_summary').value = TEXT.en.summary_default;
        handleCancerTypeChange(); 
    };
</script>
</body>
</html>
"""

# --- APP CONFIGURATION ---

# Font Registration with Fallbacks
try:
    pdfmetrics.registerFont(TTFont('Aptos', 'aptos.ttf'))
    pdfmetrics.registerFont(TTFont('Aptos-Bold', 'aptos-bold.ttf'))
    EN_FONT = 'Aptos'
    EN_FONT_B = 'Aptos-Bold'
except:
    EN_FONT = 'Helvetica'
    EN_FONT_B = 'Helvetica-Bold'

try:
    pdfmetrics.registerFont(TTFont('DengXian', 'dengxian.ttf'))
    pdfmetrics.registerFont(TTFont('DengXian-Bold', 'dengxian-bold.ttf'))
    ZH_FONT = 'DengXian'
    ZH_FONT_B = 'DengXian-Bold'
except:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    ZH_FONT = 'STSong-Light'
    ZH_FONT_B = 'STSong-Light'

# Set up Chinese font support for matplotlib
font_path = 'DengXian.ttf'
if os.path.exists(font_path):
    fm.fontManager.addfont(font_path)
    prop = fm.FontProperties(fname=font_path)
    plt.rcParams['font.family'] = prop.get_name()

plt.rcParams['axes.unicode_minus'] = False

app = Flask(__name__)
app.secret_key = 'bioarchitec_sano_2026'
CORS(app, resources={r"/api/*": {"origins": "*"}})


AUTH_FILE = 'login.csv'
LOG_FILE = 'logs.csv'

if not os.path.exists(AUTH_FILE):
    with open(AUTH_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["username", "password"])
        writer.writerow(["Admin", "BAPDO2026"])

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Action", "Username", "Time", "Testing Lab Tech", "Reviewing Examiner", "Exec Summary", "Exported Filename"])

def append_log(action, username, tech="", exam="", summary="", filename=""):
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_summary = str(summary).replace('\n', ' ') if summary else ""
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([action, username, time_str, tech, exam, safe_summary, filename])

TEXT = {
    "en": {
        "cover_company": "BioArchitec Group Limited",
        "pdf_title": "Personalized PDO Drug Sensitivity Scientific Report",
        "cover_sys": "Generated by SANO AI-Precision Oncology Platform",
        "id": "Patient ID:", "gender": "Gender / Age:",
        "diag": "Diagnosis:", "stage": "TNM Stage:", "sample": "Sample Type:", "prior": "Prior Therapy:",
        "sub_unit": "Submission Unit:", "test_unit": "Testing Unit:", "samp_sit": "Sample Situation:",
        "date": "Report Date:", "sec1": "1. Patient & Clinical Information",
        "sec2": "2. Biomarker Profile (NGS Panel)", 
        "sec3": "3. PDO Modeling Information",
        "seed_date": "Seeding Date:", "cell_count": "Cell Volume:", "medium": "Culture Medium:",
        "sec4": "4. Drug Sensitivity Matrix & Prioritization",
        "sec_sum": "Clinical Executive Summary", "chart_title": "Dose-Response IC50 Curves",
        "disclaimer_title": "Disclaimer and Terms of Use",
        "footer_conf": "Confidential - For Clinical Decision Support Use Only",
        "sig_notice": "Notice: This clinical test report is strictly invalid without the official stamp and signatures of the testing laboratory technician and the reviewing clinical examiner."
    },
    "zh": {
        "cover_company": "柏奥雅德生物科技有限公司",
        "pdf_title": "个性化类器官药物敏感性科学报告",
        "cover_sys": "由圣诺AI 肿瘤精准医疗平台生成",
        "id": "病历号:", "gender": "性别/年龄:",
        "diag": "临床诊断:", "stage": "TNM 分期:", "sample": "样本类型:", "prior": "既往治疗:",
        "sub_unit": "送检单位:", "test_unit": "检测单位:", "samp_sit": "样本状态:",
        "date": "报告日期:", "sec1": "1. 患者与临床信息",
        "sec2": "2. 生物标志物状态 (NGS Panel)",
        "sec3": "3. 类器官(PDO)建模信息",
        "seed_date": "接种日期:", "cell_count": "接种细胞量:", "medium": "培养基:",
        "sec4": "4. 药物敏感性矩阵与优先级评估",
        "sec_sum": "临床解读总结", "chart_title": "半抑制浓度 (IC50) 剂量响应曲线",
        "disclaimer_title": "免责声明与使用条款",
        "footer_conf": "机密文件 - 仅供临床辅助决策使用",
        "sig_notice": "注意：如果没有测试实验室技术员和临床审核员的正式盖章和签名，本临床测试报告严格无效。"
    }
}

DISCLAIMERS = {
    "en": [
        "i. <b>Nature of the Test (Level 2A/3 Evidence):</b> The SANO PDO test is an in vitro functional assay serving strictly as a clinical decision-support tool, not replacing MDT judgment.",
        "ii. <b>In Vitro vs. In Vivo Discrepancies:</b> In vitro cultures do not fully account for systemic pharmacokinetics, vascular perfusion, or immune responses.",
        "iii. <b>Tumor Heterogeneity:</b> Results reflect dominant cellular populations at resection time and may not predict future acquired resistance.",
        "iv. <b>Guideline Compliance:</b> Final regimens must adhere strictly to approved NCCN and CSCO standards.",
        "v. <b>Limitation of Liability:</b> BioArchitec Group assumes no legal liability for adverse clinical outcomes based on in vitro findings.",
        "vi. <b>Scope of Responsibility:</b> This test report is only responsible for the samples submitted for this specific test. Any objections or requests for clarification regarding this report must be submitted to our unit in writing within 14 days of receipt; otherwise, they will not be accepted."
    ],
    "zh": [
        "i. <b>测试性质（2A/3类证据）：</b>SANO PDO 测试是一种体外功能检测，严格作为临床辅助决策工具，不能替代 MDT 医生的判断。",
        "ii. <b>体外与体内差异：</b>体外培养无法完全反映系统的药代动力学、血管灌注或免疫反应。",
        "iii. <b>肿瘤异质性：</b>结果反映切除时的主要细胞群，不能预测未来获得性耐药。",
        "iv. <b>指南依从性：</b>最终治疗方案必须严格遵守批准的 NCCN 和 CSCO 标准。",
        "v. <b>责任限制：</b>柏奥雅德生物科技有限公司对基于体外发现的不良临床结果不承担法律责任。",
        "vi. <b>责任范围：</b>本检测报告只对本次送检样品负责。如对本检测报告有异议或需要说明，委托方应在收到报告后十四日内以书面形式向我单位提出，逾期不予受理。"
    ]
}

def log_logistic_4p(x, bottom, top, ic50, hill_slope):
    return bottom + (top - bottom) / (1 + (x / ic50)**hill_slope)

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        self.lang = kwargs.pop('lang', 'en')
        self.pat_id = kwargs.pop('pat_id', '')
        self.report_date = kwargs.pop('report_date', '')
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        font_name = ZH_FONT_B if self.lang == 'zh' else EN_FONT_B
        font_name_reg = ZH_FONT if self.lang == 'zh' else EN_FONT
        t = TEXT[self.lang]

        self.saveState()
        self.setFont("Helvetica-Bold", 36)
        self.setFillColor(colors.HexColor("#E2E8F0"), alpha=0.40)
        self.translate(letter[0] / 2.0, letter[1] / 2.0)
        self.rotate(30)
        self.drawCentredString(0, 15, "BioArchitec Group")
        self.drawCentredString(0, -25, "PDO-DST Sci. Report")
        self.restoreState()

        if self._pageNumber > 1:
            self.setFont(font_name_reg, 8)
            self.setFillColor(colors.HexColor("#0B2545"))
            
            self.drawString(54, 755, f"{t['cover_company']} | {t['cover_sys']}")
            self.drawString(54, 743, f"{t['id']} {self.pat_id}  |  {t['date']} {self.report_date}")
            
            if os.path.exists("BioArchitec logo_latest.png"):
                logo_w = 1.0 * inch
                logo_h = 0.25 * inch
                self.drawImage("BioArchitec logo_latest.png", 558 - logo_w, 742, width=logo_w, height=logo_h, mask='auto')
                
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 735, 558, 735)

            self.setFont(font_name_reg, 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawString(54, 36, t["footer_conf"] + " | Email: sano@bioarchitec.com")
            page_text = f"Page {self._pageNumber} of {page_count}" if self.lang == 'en' else f"第 {self._pageNumber} 页，共 {page_count} 页"
            self.drawRightString(558, 36, page_text)
            self.line(54, 48, 558, 48)

        self.restoreState()

def get_styles(lang):
    styles = getSampleStyleSheet()
    font_b = ZH_FONT_B if lang == "zh" else EN_FONT_B
    font_r = ZH_FONT if lang == "zh" else EN_FONT
    return {
        "title": ParagraphStyle("DocTitle", parent=styles["Heading1"], fontName=font_b, fontSize=22, leading=26, textColor=colors.HexColor("#0B2545"), alignment=1),
        "subtitle": ParagraphStyle("DocSubTitle", parent=styles["Normal"], fontName=font_r, fontSize=12, leading=16, textColor=colors.HexColor("#134074"), alignment=1),
        "h1": ParagraphStyle("SectionH1", parent=styles["Heading2"], fontName=font_b, fontSize=11, leading=14, textColor=colors.HexColor("#0B2545"), spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("BodyDark", parent=styles["Normal"], fontName=font_r, fontSize=9, leading=13, textColor=colors.HexColor("#1E293B"), spaceAfter=4),
        "th": ParagraphStyle("TableHeader", parent=styles["Normal"], fontName=font_b, fontSize=8, leading=10, textColor=colors.white, alignment=1),
        "tc": ParagraphStyle("TableCell", parent=styles["Normal"], fontName=font_r, fontSize=8, leading=10, textColor=colors.HexColor("#1E293B"), alignment=1),
        "tc_left": ParagraphStyle("TableCellLeft", parent=styles["Normal"], fontName=font_r, fontSize=8, leading=10, textColor=colors.HexColor("#1E293B"), alignment=0),
        "img_name": ParagraphStyle("ImgName", parent=styles["Normal"], fontName=font_r, fontSize=7, leading=9, textColor=colors.HexColor("#64748B"), alignment=1)
    }

def base64_to_image(b64_string, width, height):
    if "," in b64_string: b64_string = b64_string.split(",")[1]
    return RLImage(BytesIO(base64.b64decode(b64_string)), width=width, height=height, hAlign="CENTER")

@app.route('/BioArchitec%20logo_latest.png')
@app.route('/BioArchitec logo_latest.png')
def serve_logo():
    if os.path.exists('BioArchitec logo_latest.png'):
        return send_file('BioArchitec logo_latest.png')
    return "Not found", 404

# --- MODIFIED ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        req_user = request.form['username']
        req_pass = request.form['password']
        
        auth_success = False
        with open(AUTH_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['username'] == req_user and row['password'] == req_pass:
                    auth_success = True
                    break
                    
        if auth_success:
            session['logged_in'] = True
            session['username'] = req_user
            append_log("Login", req_user)
            return redirect(url_for('index'))
        else:
            flash('Invalid Credentials. Please try again.')
            
    return render_template_string(LOGIN_HTML) # Integrated login HTML

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('logged_in'): return redirect(url_for('login'))
    return render_template_string(INDEX_HTML) # Integrated main HTML

@app.route('/api/plot', methods=['POST'])
def generate_plot():
    #if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    drugs = data.get('drugs', [])
    lang = data.get('lang', 'en')
    
    plt.figure(figsize=(9, 5), dpi=200)
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(1.5)
    ax.spines['bottom'].set_linewidth(1.5)
    ax.tick_params(width=1.5)

    results = []
    for d in drugs:
        try:
            concs_raw = np.array([float(x.strip()) for x in d['concs'].split(',')])
            reps = np.array([
                [float(x.strip()) for x in d['rep1'].split(',')],
                [float(x.strip()) for x in d['rep2'].split(',')],
                [float(x.strip()) for x in d['rep3'].split(',')]
            ])
            means, stds = np.mean(reps, axis=0), np.std(reps, axis=0)
            max_inh = 100 - min(means)

            try:
                popt, _ = curve_fit(log_logistic_4p, 10.0**concs_raw, means, p0=[min(means), max(means), np.median(10.0**concs_raw), 1.0], maxfev=10000)
                calc_ic50 = popt[2]
            except: calc_ic50 = np.nan
        except Exception:
            concs_raw, means, stds, calc_ic50, max_inh = np.array([-7]), np.array([100]), np.array([0]), np.nan, 0

        disp = "N/A" if np.isnan(calc_ic50) else f"{calc_ic50:.2e}"
        cat_en = "Highly Sensitive" if max_inh >= 75 else "Sensitive" if max_inh >= 30 else "Resistant"
        cat_zh = "高度敏感" if max_inh >= 75 else "敏感" if max_inh >= 30 else "耐药"
        
        results.append({
            "name": d['name'], "ic50": calc_ic50, "ic50_display": disp,
            "inhibition": max_inh, "category": cat_zh if lang == 'zh' else cat_en
        })
        ax.errorbar(concs_raw, means, yerr=stds, fmt='-o', capsize=4, label=f"{d['name']} (IC50: {disp})")

    ax.axhline(50, color='grey', linestyle='-.')
    ax.set_xlabel("Log10 Concentration (M)", fontsize=11, fontweight='bold')
    ax.set_ylabel("Viability (%)", fontsize=11, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', frameon=False, fontsize=9)
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plot_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()
    
    results.sort(key=lambda x: x["ic50"] if not np.isnan(x["ic50"]) else float('inf'))
    return jsonify({"plot": plot_b64, "results": results})

@app.route('/api/export', methods=['POST'])
def export_pdf():
    #if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    lang = data.get('lang', 'en')
    t = TEXT[lang]
    sty = get_styles(lang)
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=72, bottomMargin=72)
    c_light_bg, c_border = colors.HexColor("#F8FAFC"), colors.HexColor("#CBD5E1")
    story = []

    story.append(Spacer(1, 1.0 * inch))
    if os.path.exists("BioArchitec logo_latest.png"):
        story.append(RLImage("BioArchitec logo_latest.png", width=3.5*inch, height=1.0*inch, hAlign="CENTER"))
    else:
        story.append(Paragraph(t["cover_company"], sty["title"]))
        
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(t["cover_sys"], sty["subtitle"]))
    story.append(Spacer(1, 1.0 * inch))
    story.append(Paragraph(t["pdf_title"], ParagraphStyle("CoverT", parent=sty["title"], fontSize=24, leading=32)))
    story.append(Spacer(1, 1.5 * inch))

    cover_info = [
        [Paragraph(f"<b>{t['id']}</b>", sty["body"]), Paragraph(data.get("patient_id", ""), sty["body"])],
        [Paragraph(f"<b>{t['diag']}</b>", sty["body"]), Paragraph(data.get("diagnosis", ""), sty["body"])],
        [Paragraph(f"<b>{t['date']}</b>", sty["body"]), Paragraph(data.get("report_date", ""), sty["body"])]
    ]
    t_cover = Table(cover_info, colWidths=[100, 200])
    t_cover.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0,0), (0,-1), "RIGHT")]))
    story.append(t_cover)
    story.append(Spacer(1, 2 * inch))
    story.append(PageBreak())

    story.append(Paragraph(t["sec_sum"], sty["h1"]))
    summary_paragraphs = []
    for line in data.get("summary_text", "").split('\n'):
        if line.strip(): summary_paragraphs.append(Paragraph(line, sty["body"]))
        
    sum_table = Table([[summary_paragraphs]], colWidths=[504])
    sum_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_light_bg),
        ("BOX", (0, 0), (-1, -1), 0.5, c_border),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph(t["sec1"], sty["h1"]))
    p_data = [
        [Paragraph(f"<b>{t['id']}</b>", sty["body"]), Paragraph(data.get("patient_id",""), sty["body"]), Paragraph(f"<b>{t['gender']}</b>", sty["body"]), Paragraph(data.get("gender_age",""), sty["body"])],
        [Paragraph(f"<b>{t['diag']}</b>", sty["body"]), Paragraph(data.get("diagnosis",""), sty["body"]), Paragraph(f"<b>{t['stage']}</b>", sty["body"]), Paragraph(data.get("stage",""), sty["body"])],
        [Paragraph(f"<b>{t['sub_unit']}</b>", sty["body"]), Paragraph(data.get("sub_unit",""), sty["body"]), Paragraph(f"<b>{t['test_unit']}</b>", sty["body"]), Paragraph(data.get("test_unit",""), sty["body"])],
        [Paragraph(f"<b>{t['samp_sit']}</b>", sty["body"]), Paragraph(data.get("samp_sit",""), sty["body"]), Paragraph(f"<b>{t['sample']}</b>", sty["body"]), Paragraph(data.get("sample_type",""), sty["body"])],
        [Paragraph(f"<b>{t['prior']}</b>", sty["body"]), Paragraph(data.get("prior_therapy",""), sty["body"]), Paragraph(f"<b>{t['date']}</b>", sty["body"]), Paragraph(data.get("report_date",""), sty["body"])],
        [Paragraph("<b>Turnaround Time:</b>" if lang=='en' else "<b>检测周期:</b>", sty["body"]), Paragraph("7 Days" if lang=='en' else "7天", sty["body"]), Paragraph("", sty["body"]), Paragraph("", sty["body"])]
    ]
    tp = Table(p_data, colWidths=[105, 147, 105, 147])
    tp.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), c_light_bg), ("BOX", (0, 0), (-1, -1), 0.5, c_border), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(tp)
    
    if data.get("surg_image") and len(data["surg_image"]) > 0:
        story.append(Spacer(1, 8))
        img_obj = data["surg_image"][0]
        img = base64_to_image(img_obj['b64'], 2.5*inch, 1.8*inch)
        f_name = Paragraph(img_obj['name'], sty['img_name'])
        story.append(KeepTogether([img, Spacer(1, 4), f_name]))
    story.append(Spacer(1, 10))

    story.append(Paragraph(t["sec2"], sty["h1"]))
    b_items = data.get("biomarkers", [])
    b_data = []
    for i in range(0, len(b_items), 2):
        row = [Paragraph(f"<b>{b_items[i]['name']}:</b>", sty["body"]), Paragraph(b_items[i]['val'], sty["body"])]
        if i+1 < len(b_items):
            row.extend([Paragraph(f"<b>{b_items[i+1]['name']}:</b>", sty["body"]), Paragraph(b_items[i+1]['val'], sty["body"])])
        else:
            row.extend([Paragraph("", sty["body"]), Paragraph("", sty["body"])])
        b_data.append(row)
        
    if b_data:
        tb = Table(b_data, colWidths=[105, 147, 105, 147])
        tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), c_light_bg), ("BOX", (0, 0), (-1, -1), 0.5, c_border), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story.append(tb)
    story.append(Spacer(1, 10))

    story.append(Paragraph(t["sec3"], sty["h1"]))
    m_data = [
        [Paragraph(f"<b>{t['seed_date']}</b>", sty["body"]), Paragraph(data.get("seed_date",""), sty["body"]), Paragraph(f"<b>{t['cell_count']}</b>", sty["body"]), Paragraph(data.get("cell_count",""), sty["body"])],
        [Paragraph(f"<b>{t['medium']}</b>", sty["body"]), Paragraph(data.get("medium",""), sty["body"]), Paragraph("", sty["body"]), Paragraph("", sty["body"])]
    ]
    tm = Table(m_data, colWidths=[105, 147, 105, 147])
    tm.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), c_light_bg), ("BOX", (0, 0), (-1, -1), 0.5, c_border), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(tm)
    
    if data.get("pdo_images") and len(data["pdo_images"]) > 0:
        story.append(Spacer(1, 10))
        img_row, name_row = [], []
        for img_obj in data["pdo_images"][:3]:
            img_row.append(base64_to_image(img_obj['b64'], 2*inch, 1.5*inch))
            name_row.append(Paragraph(img_obj['name'], sty['img_name']))
        
        t_imgs = Table([img_row, name_row])
        t_imgs.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t_imgs)
            
    story.append(Spacer(1, 10))

    story.append(Paragraph(t["sec4"], sty["h1"]))
    d_rows = [[Paragraph("Rank", sty["th"]), Paragraph("Regimen", sty["th"]), Paragraph("IC50 (M)", sty["th"]), Paragraph("Max Inhib.", sty["th"]), Paragraph("Category", sty["th"])]]
    for idx, d in enumerate(data.get("results", [])):
        cat_color = "#15803D" if d["category"] in ["Highly Sensitive", "高度敏感"] else "#16A34A" if d["category"] in ["Sensitive", "敏感"] else "#DC2626"
        d_rows.append([Paragraph(str(idx + 1), sty["tc"]), Paragraph(d["name"], sty["tc_left"]), Paragraph(d["ic50_display"], sty["tc"]), Paragraph(f"{d['inhibition']:.1f}%", sty["tc"]), Paragraph(f'<font color="{cat_color}"><b>{d["category"]}</b></font>', sty["tc"])])
        
    td = Table(d_rows, colWidths=[40, 150, 100, 100, 114])
    td.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B2545")), ("BOX", (0, 0), (-1, -1), 0.5, c_border), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0"))]))
    story.append(td)
    
    story.append(PageBreak())
    story.append(Paragraph(t["chart_title"], sty["h1"]))
    if data.get("plot_b64"): story.append(base64_to_image(data.get("plot_b64"), 7.0*inch, 4.0*inch))

    story.append(Spacer(1, 20))
    story.append(Paragraph(t["disclaimer_title"], sty["h1"]))
    for disc in DISCLAIMERS[lang]:
        story.append(Paragraph(disc, sty["body"]))
    story.append(Spacer(1, 15))

    story.append(Paragraph(f"<i>{t['sig_notice']}</i>", ParagraphStyle("Notice", parent=sty["body"], textColor=colors.HexColor("#DC2626"), alignment=1)))
    story.append(Spacer(1, 15))

    story.append(HRFlowable(width="100%", thickness=0.5, color=c_border, spaceBefore=4, spaceAfter=8))
    t_lbl = "Testing Laboratory Technician:" if lang=='en' else "测试实验室技术员:"
    e_lbl = "Reviewing Clinical Examiner:" if lang=='en' else "临床审核员:"
    sig_line = "Signature: ______________________" if lang=='en' else "签名: ______________________"
    date_line = "Date: ____ / ____ / ________" if lang=='en' else "日期: ____ / ____ / ________"

    sig_data = [
        [Paragraph(f"<b>{t_lbl}</b>", sty["body"]), Paragraph(f"<b>{e_lbl}</b>", sty["body"])],
        [Paragraph(f"<br/><br/>{sig_line}<br/>{data.get('tech_name', '')}", sty["body"]), Paragraph(f"<br/><br/>{sig_line}<br/>{data.get('exam_name', '')}", sty["body"])],
        [Paragraph(date_line, sty["body"]), Paragraph(date_line, sty["body"])],
    ]
    t_sig = Table(sig_data, colWidths=[252, 252])
    t_sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(KeepTogether([t_sig]))

    def canvas_maker(*args, **kwargs):
        kwargs['lang'] = lang
        kwargs['pat_id'] = data.get("patient_id", "")
        kwargs['report_date'] = data.get("report_date", "")
        return NumberedCanvas(*args, **kwargs)

    doc.build(story, canvasmaker=canvas_maker)
    buffer.seek(0)
    
    dl_name = data.get('dl_name', 'report.pdf')
    append_log("Export PDF", session.get('username'), data.get('tech_name'), data.get('exam_name'), data.get('summary_text'), dl_name)
    
    return send_file(buffer, as_attachment=True, download_name=dl_name, mimetype='application/pdf')

if __name__ == "__main__":
    # Only run flaskwebgui locally; cloud servers use gunicorn
    try:
        from flaskwebgui import FlaskUI
        FlaskUI(app=app, server="flask", port=5000, width=1200, height=800).run()
    except ImportError:
        app.run(host="0.0.0.0", port=5000)
