1. Find Input.xlsm and place it in the Input folder. There should preferrably be no other files in this folder.
2. Fill Input.xlsm worksheets as per the instructions in the workbook. (Use excel macros 'Generate Sessions' and 'Generate Dump' in that order to generate csv output for the scheduler process.
3. The dump files should be created in the Input folder.
4. Launch 'Import.exe' or 'python Import.py' to start the generator. The generator will consume the csv configuration dump to define the model and try to optimally solve it given the constraints.
5. The output should be available in Output folder.

PS: If you choose to run the exe, you will have to monitor either the output folder or the task manager to know when the job has finished.
