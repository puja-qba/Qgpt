from openpyxl import load_workbook


class ExcelReader:

    @staticmethod
    def read_excel(file_path, sheet_name):

        workbook = load_workbook(file_path)
        sheet = workbook[sheet_name]

        data = []

        headers = [cell.value for cell in sheet[1]]

        for row in sheet.iter_rows(min_row=2, values_only=True):

            row_data = dict(zip(headers, row))
            data.append(row_data)

        return data
