import pandas
import numpy
import networkx

import config

import pyexcel
import pyexcel.ext.xls
import pyexcel.ext.xlsx

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.config.from_object(config)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST' and 'excel' in request.files:

        # handle file upload
        filename = request.files['excel'].filename
        extension = filename.split(".")[1]

        # parse file into excel data
        sheet = pyexcel.get_sheet(file_type=extension, file_content=request.files['excel'].read())

        # column and row titles
        title = sheet[0, 0]
        agents = [k for k in sheet.column[0] if k != sheet[0, 0]]
        types = [k for k in sheet.row[0] if 'Weight' not in k and k != sheet[0, 0]]

        # name sheet columns and create objects
        sheet.name_columns_by_row(0)
        records = pyexcel.to_records(sheet)

        # all organization values and weights
        organizations = set()
        weights = {}
        data = {}
        for record in records:
            for key, value in record.items():
                if 'Weight' in key:
                    _index = key.index('Weight') - 1
                    _key = key[:_index]
                    weights[_key] = value
                    pass
                elif value and value not in agents:
                    if value not in data:
                        data[value] = {}
                    data[value][record[title]] = record[key + ' Weight']
                    organizations.add(value)

        # build data frame to hold information
        df1 = pandas.DataFrame(index=agents, columns=organizations, data=data).fillna(0)

        # transpose data frame
        df2 = df1.T

        # convert data frames to matrix
        m1 = df1.as_matrix()
        m2 = df2.as_matrix()

        # conduct matrix multipleication
        m3 = numpy.dot(m1, m2)
        m4 = numpy.dot(m2, m1)

        # fix multiplication, zero-ing agent-to-themselves
        df3 = pandas.DataFrame(index=agents, columns=agents, data=m3)
        for agent in agents:
            df3[agent][agent] = 0

        # fix multiplication, zero-ing organization-to-themselves
        df4 = pandas.DataFrame(index=organizations, columns=organizations, data=m4)
        for organization in organizations:
            df4[organization][organization] = 0

        # testing results
        # print agents
        # print organizations
        # print weights
        # print data

        print df1
        print df2

        # print m1
        # print m2

        print df1.index
        print df1.columns

        # print m3
        # print m4

        print df3
        print df4


        # network 1
        n1 = networkx.Graph()
        n1.add_nodes_from(agents)
        n1.add_nodes_from(organizations)
        for organization in organizations:
            for agent in agents:
                weight = df1[organization][agent]
                if weight:
                    n1.add_edge(agent, organization, weight=weight)

        # network 2
        n2 = networkx.Graph()
        n2.add_nodes_from(agents)
        n2.add_nodes_from(organizations)
        for agent in agents:
            for organization in organizations:
                weight = df2[agent][organization]
                if weight:
                    n2.add_edge(organization, agent, weight=weight)

        # network 3
        n3 = networkx.Graph()
        n3.add_nodes_from(agents)
        for agent1 in agents:
            for agent2 in agents:
                if not (agent1 in n3 and agent2 in n3[agent1]):
                    weight = df3[agent1][agent2]
                    if weight:
                        n3.add_edge(agent1, agent2, weight=weight)

        # network 4
        n4 = networkx.Graph()
        n4.add_nodes_from(organizations)
        for organization1 in organizations:
            for organization2 in organizations:
                if not (organization1 in n4 and organization2 in n4[organization1]):
                    weight = df4[organization1][organization2]
                    if weight:
                        n4.add_edge(organization1, organization2, weight=weight)

        i3 = networkx.eigenvector_centrality_numpy(n3)
        c3 = networkx.betweenness_centrality(n3)

        i4 = networkx.eigenvector_centrality_numpy(n4)
        c4 = networkx.betweenness_centrality(n4)





        import matplotlib.pyplot as plt
        networkx.draw(n4, with_labels=True)
        plt.savefig('plot-n4.png')

        # networkx.draw(n4)
        # plt.savefig('plot-n4.png')


        # respond with a json
        return jsonify({
            "data": data,
            "agents": agents,
            "organizations": list(organizations),
            "weights": weights,
            "agent influencer": i3,
            "agent connector": c3,
            "organization influencer": i4,
            "organization connector": c4
        })

    return render_template('index.html')

