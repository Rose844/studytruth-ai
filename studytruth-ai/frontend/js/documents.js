async function loadDocumentsPage() {
  const root = document.getElementById("page-documents");

  root.innerHTML = `
    <div class="topbar">

      <div class="page-head-row">

        <span class="page-icon page-icon-green">
          ${ICONS.docs}
        </span>

        <div>

          <h1>
            My Documents
          </h1>

          <p class="subtitle">
            Upload your syllabus, notes, PYQs and more — organized by subject and authority.
          </p>

        </div>

      </div>

    </div>


    <div
      class="grid"
      style="grid-template-columns:340px 1fr;align-items:start;">

      <div class="card">

        <div class="section-title">
          Upload a document
        </div>

        <form id="upload-form">

          <div
            class="upload-dropzone"
            id="dropzone">

            ${ICONS.upload}

            <div id="dropzone-label">
              Drag & drop a file, or click to browse
            </div>

            <input
              type="file"
              id="file-input"
              accept=".pdf,.txt"
              style="display:none;"
            />

          </div>


          <div class="field mt-16">

            <label>
              Subject
            </label>

            <input
              list="subject-datalist"
              id="f-subject"
              placeholder="e.g. Computer Networks"
              required
            />

            <datalist id="subject-datalist"></datalist>

          </div>


          <div class="field">

            <label>
              Document type
            </label>

            <select
              id="f-doctype"
              required>

              <option value="syllabus">
                Syllabus
              </option>

              <option value="lecture_notes">
                Lecture Notes
              </option>

              <option value="faculty_material">
                Faculty Material
              </option>

              <option value="assignment">
                Assignment
              </option>

              <option value="pyq">
                Previous Year Questions
              </option>

              <option value="lab_manual">
                Lab Manual
              </option>

              <option value="exam_instructions">
                Exam Instructions
              </option>

              <option value="notice">
                College Notice
              </option>

              <option value="other">
                Other
              </option>

            </select>

          </div>


          <div
            class="grid grid-2"
            style="gap:10px;">

            <div class="field">

              <label>
                Academic year
              </label>

              <input
                id="f-year"
                value="2025-26"
              />

            </div>


            <div class="field">

              <label>
                Version
              </label>

              <input
                id="f-version"
                value="v1"
              />

            </div>

          </div>


          <button
            type="submit"
            class="btn btn-primary w-full"
            id="upload-btn">

            ${ICONS.upload}

            Upload & Index

          </button>

        </form>

      </div>


      <div class="card">

        <div class="section-title">

          <span>

            All documents

            <span
              class="text-muted text-sm"
              style="font-weight:600;margin-left:6px;"
              id="doc-count-label">
            </span>

          </span>


          <div class="flex gap-8">

            <select
              id="doc-filter-subject"
              data-subject-select
              style="width:170px;">
            </select>

            <input
              id="doc-search"
              class="input"
              placeholder="Search documents..."
              style="width:180px;"
            />

          </div>

        </div>


        <div id="doc-list">
          ${skeletonRows(4, 50)}
        </div>

      </div>

    </div>
  `;


  const fileInput =
    document.getElementById("file-input");

  const dropzone =
    document.getElementById("dropzone");

  const label =
    document.getElementById("dropzone-label");


  dropzone.addEventListener(
    "click",
    () => fileInput.click()
  );


  fileInput.addEventListener(
    "change",
    () => {

      if (fileInput.files[0]) {

        label.textContent =
          fileInput.files[0].name;

      }

    }
  );


  ["dragover", "dragleave", "drop"]
    .forEach(
      (evt) =>
        dropzone.addEventListener(
          evt,
          (e) => e.preventDefault()
        )
    );


  dropzone.addEventListener(
    "dragover",
    () =>
      dropzone.classList.add("dragover")
  );


  dropzone.addEventListener(
    "dragleave",
    () =>
      dropzone.classList.remove("dragover")
  );


  dropzone.addEventListener(
    "drop",
    (e) => {

      dropzone.classList.remove(
        "dragover"
      );

      if (e.dataTransfer.files[0]) {

        fileInput.files =
          e.dataTransfer.files;

        label.textContent =
          e.dataTransfer.files[0].name;

      }

    }
  );


  document
    .getElementById("upload-form")
    .addEventListener(
      "submit",
      handleUpload
    );


  document
    .getElementById("doc-filter-subject")
    .addEventListener(
      "change",
      renderDocList
    );


  document
    .getElementById("doc-search")
    .addEventListener(
      "input",
      renderDocList
    );


  document.getElementById(
    "subject-datalist"
  ).innerHTML =
    STATE.subjects
      .map(
        (s) =>
          `<option value="${escapeHtml(s)}"></option>`
      )
      .join("");


  populateSubjectSelects();

  await refreshSubjects();


  document.getElementById(
    "subject-datalist"
  ).innerHTML =
    STATE.subjects
      .map(
        (s) =>
          `<option value="${escapeHtml(s)}"></option>`
      )
      .join("");


  renderDocList();
}


function renderDocList() {

  const el =
    document.getElementById("doc-list");

  const filterSubject =
    document.getElementById(
      "doc-filter-subject"
    ).value;

  const query =
    (
      document.getElementById(
        "doc-search"
      ).value || ""
    )
      .toLowerCase()
      .trim();


  let docs = STATE.documents;


  if (filterSubject) {

    docs =
      docs.filter(
        (d) =>
          d.subject === filterSubject
      );

  }


  if (query) {

    docs =
      docs.filter(
        (d) =>
          d.filename
            .toLowerCase()
            .includes(query) ||
          (d.preview || "")
            .toLowerCase()
            .includes(query)
      );

  }


  document.getElementById(
    "doc-count-label"
  ).textContent =
    `(${docs.length} document${
      docs.length !== 1
        ? "s"
        : ""
    })`;


  if (!docs.length) {

    el.innerHTML = stateBlock({
      icon: "docs",
      title: "No documents found",
      body:
        "Try a different search, or use the form on the left to upload your first study document."
    });

    return;
  }


  const bySubject = {};


  docs.forEach(
    (d) => {

      (
        bySubject[d.subject] =
          bySubject[d.subject] || []
      ).push(d);

    }
  );


  el.innerHTML =
    Object.entries(bySubject)
      .map(
        ([subject, list]) => `
          <div style="margin-bottom:18px;">

            <div
              style="
                font-weight:700;
                font-size:13px;
                color:var(--text-secondary);
                margin-bottom:8px;
              ">

              ${escapeHtml(subject)}

            </div>


            <table class="doc-table">

              <thead>

                <tr>

                  <th>
                    Document
                  </th>

                  <th>
                    Type
                  </th>

                  <th>
                    Version
                  </th>

                  <th>
                    Date
                  </th>

                  <th>
                    Authority
                  </th>

                </tr>

              </thead>


              <tbody>

                ${list
                  .map(
                    (d) => `
                      <tr>

                        <td>

                          <div
                            class="flex items-center gap-8">

                            <span
                              class="doc-icon"
                              style="
                                width:32px;
                                height:32px;
                                border-radius:9px;
                              ">

                              ${ICONS.file}

                            </span>


                            <div>

                              <div class="doc-name">

                                ${escapeHtml(
                                  d.filename
                                )}

                              </div>


                              <div class="doc-preview">

                                ${escapeHtml(
                                  (
                                    d.preview || ""
                                  ).slice(0, 90)
                                )}

                                ${
                                  (
                                    d.preview || ""
                                  ).length > 90
                                    ? "…"
                                    : ""
                                }

                              </div>

                            </div>

                          </div>

                        </td>


                        <td>

                          <span
                            class="pill pill-indigo">

                            ${
                              DOC_TYPE_LABEL[
                                d.doc_type
                              ] ||
                              d.doc_type
                            }

                          </span>

                        </td>


                        <td class="text-sm">

                          ${escapeHtml(
                            d.version
                          )}

                        </td>


                        <td class="text-sm">

                          ${fmtDate(
                            d.upload_date
                          )}

                        </td>


                        <td>

                          <span
                            class="pill authority-rank-${d.authority_rank}">

                            ${authorityLabel(
                              d.authority_rank
                            )}

                          </span>

                        </td>

                      </tr>
                    `
                  )
                  .join("")}

              </tbody>

            </table>

          </div>
        `
      )
      .join("");
}


async function handleUpload(e) {

  e.preventDefault();


  const fileInput =
    document.getElementById(
      "file-input"
    );

  const file =
    fileInput.files[0];


  if (!file) {

    toast(
      "Please choose a file first",
      "error"
    );

    return;
  }


  const btn =
    document.getElementById(
      "upload-btn"
    );


  btn.disabled = true;

  btn.innerHTML = `
    <div class="spinner"></div>
    Uploading & indexing...
  `;


  const formData =
    new FormData();


  formData.append(
    "file",
    file
  );


  formData.append(
    "subject",
    document.getElementById(
      "f-subject"
    ).value
  );


  formData.append(
    "doc_type",
    document.getElementById(
      "f-doctype"
    ).value
  );


  formData.append(
    "academic_year",
    document.getElementById(
      "f-year"
    ).value
  );


  formData.append(
    "version",
    document.getElementById(
      "f-version"
    ).value
  );


  try {

    await api.uploadDocument(
      formData
    );


    toast(
      "Document uploaded and indexed successfully",
      "success"
    );


    document
      .getElementById(
        "upload-form"
      )
      .reset();


    document.getElementById(
      "dropzone-label"
    ).textContent =
      "Drag & drop a file, or click to browse";


    await refreshSubjects();

    renderDocList();

  } catch (err) {

    toast(
      err.message,
      "error"
    );

  } finally {

    btn.disabled = false;

    btn.innerHTML = `
      ${ICONS.upload}
      Upload & Index
    `;

  }
}